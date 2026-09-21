import logging
import threading
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core import background


class RunInBackgroundTests(SimpleTestCase):
    @override_settings(BACKGROUND_TASKS_ASYNC=False)
    def test_runs_inline_on_the_callers_thread_when_async_is_off(self):
        seen = []

        background.run_in_background(lambda: seen.append(threading.current_thread()), name="inline-job")

        self.assertEqual(seen, [threading.current_thread()])

    @override_settings(BACKGROUND_TASKS_ASYNC=False)
    def test_inline_mode_never_closes_the_callers_database_connection(self):
        """A test's wrapping transaction (or its in-memory database) lives on
        the caller's connection; closing it would end the test."""
        with patch.object(background.connections, "close_all") as close_all:
            background.run_in_background(lambda: None, name="inline-job")

        close_all.assert_not_called()

    @override_settings(BACKGROUND_TASKS_ASYNC=True)
    def test_runs_on_a_named_pool_thread_when_async_is_on(self):
        done = threading.Event()
        seen = {}

        def work():
            seen["thread"] = threading.current_thread().name
            done.set()

        background.run_in_background(work, name="pool-job", pool="unit-test-pool", workers=2)

        self.assertTrue(done.wait(5), "the job never ran")
        self.assertNotEqual(seen["thread"], threading.current_thread().name)
        self.assertTrue(seen["thread"].startswith("bg-unit-test-pool"), seen["thread"])

    @override_settings(BACKGROUND_TASKS_ASYNC=True)
    def test_a_pool_is_bounded(self):
        """A bulk import that creates hundreds of parents must queue behind a
        couple of workers, not open hundreds of provider connections."""
        background.run_in_background(lambda: None, name="warm-up", pool="bounded-pool", workers=2)

        self.assertEqual(background._POOLS["bounded-pool"]._max_workers, 2)

    @override_settings(BACKGROUND_TASKS_ASYNC=True)
    def test_a_pool_thread_closes_its_own_database_connections_when_done(self):
        done = threading.Event()
        closed = []

        def close_all():
            closed.append(threading.current_thread().name)

        with patch.object(background.connections, "close_all", side_effect=close_all):
            background.run_in_background(done.set, name="cleanup-job", pool="cleanup-pool")
            self.assertTrue(done.wait(5))
            # close_all runs in the worker's finally, just after the work returns.
            for _ in range(50):
                if closed:
                    break
                threading.Event().wait(0.1)

        self.assertEqual(len(closed), 1)
        self.assertTrue(closed[0].startswith("bg-cleanup-pool"))

    @override_settings(BACKGROUND_TASKS_ASYNC=False)
    def test_a_failing_job_is_logged_and_never_raised(self):
        def explode():
            raise RuntimeError("provider on fire")

        with self.assertLogs("core.background", level=logging.ERROR) as captured:
            background.run_in_background(explode, name="exploding-job")  # must not raise

        self.assertIn("exploding-job", "\n".join(captured.output))
        self.assertIn("provider on fire", "\n".join(captured.output))


class RunInBackgroundLaterTests(SimpleTestCase):
    @override_settings(BACKGROUND_TASKS_ASYNC=True)
    def test_schedules_a_daemon_timer_for_the_delay(self):
        with patch("core.background.threading.Timer") as timer_cls:
            background.run_in_background_later(20, lambda: None, name="retry-job", pool="later-pool")

        timer_cls.assert_called_once()
        self.assertEqual(timer_cls.call_args.args[0], 20)
        timer = timer_cls.return_value
        self.assertTrue(timer.daemon)
        timer.start.assert_called_once()

    @override_settings(BACKGROUND_TASKS_ASYNC=True)
    def test_a_fired_timer_hands_the_job_to_the_pool(self):
        done = threading.Event()
        with patch("core.background.threading.Timer") as timer_cls:
            background.run_in_background_later(5, done.set, name="retry-job", pool="later-pool")
        fire, args = timer_cls.call_args.args[1], timer_cls.call_args.kwargs["args"]

        fire(*args)  # what the timer thread does when the delay elapses

        self.assertTrue(done.wait(5), "the retry never ran")

    @override_settings(BACKGROUND_TASKS_ASYNC=False)
    def test_does_nothing_under_the_test_runner(self):
        """A timer firing minutes later would touch a torn-down test database."""
        with patch("core.background.threading.Timer") as timer_cls:
            background.run_in_background_later(20, lambda: None, name="retry-job")

        timer_cls.assert_not_called()
