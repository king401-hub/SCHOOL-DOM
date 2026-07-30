from unittest.mock import patch

from django.test import TestCase

from core.models import SchoolTenant
from notifications.models import Notification
from request_queue.exceptions import RequestRejectedError, RetriableRequestError
from request_queue.models import QueuedRequest, QueuedRequestEvent
from request_queue.services import backoff_seconds, cancel_request, enqueue_request, finalize_terminal, manual_retry
from request_queue.tasks import process_queued_request
from users.models import User


def _make_user(school, email):
    return User.objects.create_user(
        email=email,
        password="Pass12345",
        first_name="Queue",
        last_name="User",
        role="school_admin",
        tenant=school,
        is_active=True,
        is_verified=True,
    )


class EnqueueDedupeTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Queue School", schema_name="queue_school", is_active=True)
        self.user = _make_user(self.school, "queue.user@school.edu")

    def test_new_request_is_queued_and_logged(self):
        request, created = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        self.assertTrue(created)
        self.assertEqual(request.status, QueuedRequest.STATUS_QUEUED)
        self.assertEqual(
            list(request.history.values_list("event_type", flat=True)),
            [QueuedRequestEvent.EVENT_CREATED, QueuedRequestEvent.EVENT_QUEUED],
        )

    def test_duplicate_submission_is_linked_and_cancelled(self):
        original, created = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        resolved, created_again = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(resolved.id, original.id)

        linked = QueuedRequest.objects.filter(linked_request=original)
        self.assertEqual(linked.count(), 1)
        self.assertEqual(linked.first().status, QueuedRequest.STATUS_CANCELLED)
        self.assertTrue(linked.first().is_archived)

    def test_different_payload_is_not_deduped(self):
        _, created_a = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        _, created_b = enqueue_request(self.school, self.user, "test_type", {"amount": "200"})
        self.assertTrue(created_a)
        self.assertTrue(created_b)
        self.assertEqual(QueuedRequest.objects.filter(is_archived=False).count(), 2)

    def test_second_duplicate_also_links_to_the_same_original(self):
        original, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        enqueue_request(self.school, self.user, "test_type", {"amount": "100"})

        self.assertEqual(QueuedRequest.objects.filter(linked_request=original).count(), 2)

    def test_dedupe_payload_ignores_a_freshly_generated_field(self):
        _, created_a = enqueue_request(
            self.school, self.user, "test_type", {"amount": "100", "nonce": "aaa"},
            dedupe_payload={"amount": "100"},
        )
        _, created_b = enqueue_request(
            self.school, self.user, "test_type", {"amount": "100", "nonce": "bbb"},
            dedupe_payload={"amount": "100"},
        )
        self.assertTrue(created_a)
        self.assertFalse(created_b)


class FinalizeTerminalTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Finalize School", schema_name="finalize_school", is_active=True)
        self.user = _make_user(self.school, "finalize.user@school.edu")

    def test_approving_original_archives_duplicates_and_notifies_once(self):
        original, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        enqueue_request(self.school, self.user, "test_type", {"amount": "100"})

        finalize_terminal(original, QueuedRequest.STATUS_APPROVED, description="done")

        original.refresh_from_db()
        self.assertEqual(original.status, QueuedRequest.STATUS_APPROVED)
        duplicates = QueuedRequest.objects.filter(linked_request=original)
        self.assertEqual(duplicates.count(), 2)
        self.assertTrue(all(d.is_archived for d in duplicates))
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_failed_notifies_requester(self):
        original, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "100"})
        finalize_terminal(original, QueuedRequest.STATUS_FAILED, description="boom")
        self.assertEqual(Notification.objects.filter(user=self.user, notification_type="alert").count(), 1)


class AdminActionTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Action School", schema_name="action_school", is_active=True)
        self.user = _make_user(self.school, "action.user@school.edu")

    def test_manual_retry_only_allowed_from_failed(self):
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"})
        with self.assertRaises(ValueError):
            manual_retry(request, actor=self.user)

        request.status = QueuedRequest.STATUS_FAILED
        request.save(update_fields=["status"])
        manual_retry(request, actor=self.user)
        request.refresh_from_db()
        self.assertEqual(request.status, QueuedRequest.STATUS_QUEUED)

    def test_cancel_blocks_terminal_requests(self):
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"})
        request.status = QueuedRequest.STATUS_APPROVED
        request.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            cancel_request(request, actor=self.user)


class BackoffTests(TestCase):
    def test_backoff_grows_and_caps(self):
        self.assertEqual(backoff_seconds(1), 60)
        self.assertEqual(backoff_seconds(2), 120)
        self.assertEqual(backoff_seconds(10), 3600)


class ProcessQueuedRequestTaskTests(TestCase):
    """Exercises the Celery task directly (not via .delay()) - a bound task
    invoked outside a worker sets request.called_directly, so self.retry()
    re-raises rather than needing a real broker connection."""

    def setUp(self):
        self.school = SchoolTenant.objects.create(name="Task School", schema_name="task_school", is_active=True)
        self.user = _make_user(self.school, "task.user@school.edu")

    @patch("request_queue.tasks.get_handler")
    def test_retries_then_succeeds(self, mock_get_handler):
        attempts = {"count": 0}

        def flaky_handler(queued_request):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RetriableRequestError("temporary provider timeout")
            return {"ok": True}

        mock_get_handler.return_value = flaky_handler
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"}, max_retries=5)

        for _ in range(2):
            with self.assertRaises(Exception):
                process_queued_request(str(request.id))
            request.refresh_from_db()
            self.assertEqual(request.status, QueuedRequest.STATUS_RETRYING)

        result = process_queued_request(str(request.id))
        request.refresh_from_db()
        self.assertEqual(result["status"], "approved")
        self.assertEqual(request.status, QueuedRequest.STATUS_APPROVED)
        self.assertEqual(request.result, {"ok": True})
        self.assertEqual(attempts["count"], 3)

    @patch("request_queue.tasks.get_handler")
    def test_exhausting_retries_marks_failed(self, mock_get_handler):
        def always_fails(queued_request):
            raise RetriableRequestError("still down")

        mock_get_handler.return_value = always_fails
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"}, max_retries=2)

        # First attempt: retry_count -> 1, still below max_retries -> retries (raises).
        with self.assertRaises(Exception):
            process_queued_request(str(request.id))
        request.refresh_from_db()
        self.assertEqual(request.status, QueuedRequest.STATUS_RETRYING)

        # Second attempt: retry_count -> 2, hits max_retries -> terminal failure,
        # returns normally instead of raising (no more retries to schedule).
        result = process_queued_request(str(request.id))
        request.refresh_from_db()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(request.status, QueuedRequest.STATUS_FAILED)
        self.assertEqual(request.retry_count, 2)

    @patch("request_queue.tasks.get_handler")
    def test_rejection_is_terminal_without_retry(self, mock_get_handler):
        def rejects(queued_request):
            raise RequestRejectedError("bad input")

        mock_get_handler.return_value = rejects
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"})

        result = process_queued_request(str(request.id))
        request.refresh_from_db()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(request.status, QueuedRequest.STATUS_REJECTED)

    @patch("request_queue.tasks.get_handler")
    def test_already_terminal_request_is_a_no_op(self, mock_get_handler):
        request, _ = enqueue_request(self.school, self.user, "test_type", {"amount": "1"})
        request.status = QueuedRequest.STATUS_APPROVED
        request.save(update_fields=["status"])

        result = process_queued_request(str(request.id))
        mock_get_handler.assert_not_called()
        self.assertEqual(result["reason"], "already_terminal")
