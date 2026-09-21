"""Run best-effort work off the request thread, without needing Celery.

Why this exists: this project has no confirmed Celery worker in production.
Calling ``task.delay()`` there fails in one of two ways:

* no broker - ``.delay()`` blocks ~110 seconds retrying the connection before
  it raises, so the HTTP request that triggered it hangs until the web server
  kills it;
* a broker but no worker - ``.delay()`` "succeeds" and the task sits in the
  queue forever, with nothing to show for it.

For short jobs that must not hold up a request (texting a parent a receipt,
provisioning a parent's virtual account) a small in-process thread pool has
neither failure mode. Nothing here is durable across a restart, so callers
must leave a record of unfinished work that a person or a sweep can pick up
(receipts do: the status columns on the payment).

Pools are bounded and named, so a bulk import that creates hundreds of parents
queues behind a couple of workers instead of opening hundreds of connections
to a payment provider at once, and slow provisioning can never starve
receipts.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connection, connections

logger = logging.getLogger(__name__)

_POOLS = {}
_POOLS_LOCK = threading.Lock()


def _async_enabled():
    """False under the test runner (see settings.BACKGROUND_TASKS_ASYNC).

    A worker thread opens its own database connection, so it cannot see the
    uncommitted rows of a test's wrapping transaction. In that mode work runs
    inline instead, which is also what makes it deterministic to assert on.
    """
    return getattr(settings, "BACKGROUND_TASKS_ASYNC", True)


def _pool(name, workers):
    with _POOLS_LOCK:
        pool = _POOLS.get(name)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"bg-{name}")
            _POOLS[name] = pool
        return pool


def _wrap(work, name, schema_name):
    """`work` plus the housekeeping every background task needs."""
    scheduled_from = threading.current_thread()

    def _runner():
        # False when the work runs inline on the caller's own thread (the test
        # runner): that thread's connection is the caller's, and closing it
        # would end the caller's transaction - or, for an in-memory test
        # database, delete the database.
        own_thread = threading.current_thread() is not scheduled_from
        try:
            # A pool thread has its own connection: carry over the tenant
            # schema the request was using (a no-op unless django-tenants is
            # active).
            if own_thread and schema_name and hasattr(connection, "set_schema"):
                connection.set_schema(schema_name)
            work()
        except Exception:
            logger.exception("Background task %s failed", name)
        finally:
            if own_thread:
                connections.close_all()

    return _runner


def _submit(runner, name, pool, workers):
    try:
        _pool(pool, workers).submit(runner)
    except RuntimeError:
        # The interpreter is shutting down; nothing more can be scheduled.
        logger.warning("Background task %s dropped: the process is shutting down.", name)


def run_in_background(work, name="background-task", pool="default", workers=4):
    """Run ``work()`` soon, off the calling thread. Never raises."""
    runner = _wrap(work, name, getattr(connection, "schema_name", None))
    if not _async_enabled():
        runner()
        return
    _submit(runner, name, pool, workers)


def run_in_background_later(delay_seconds, work, name="background-task", pool="default", workers=4):
    """Run ``work()`` in the background after ``delay_seconds``. Never raises.

    Used for automatic retries. The timer is a daemon thread, so a retry that
    has not fired yet is simply lost if the process exits first - which is why
    the state that matters lives in the database. Does nothing under the test
    runner, where a timer firing minutes later would touch a torn-down
    database; tests capture this function to assert on what was scheduled.
    """
    if not _async_enabled():
        return
    # Wrapped now, on the calling thread, because that is the thread that
    # knows the tenant schema; the timer thread that fires later does not.
    runner = _wrap(work, name, getattr(connection, "schema_name", None))
    timer = threading.Timer(delay_seconds, _submit, args=(runner, name, pool, workers))
    timer.daemon = True
    timer.name = f"{name}-timer"
    timer.start()
