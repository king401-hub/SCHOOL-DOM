"""Permanent, read-only student archive (the Alumni module).

The archive has to outlive the student it describes. Deleting a student today
runs `student_user.delete()`, and every record that matters here -
StudentProfile, subject scores, fees, attendance - hangs off that row by
CASCADE, so a delete wipes the history along with the account. That is why an
ArchivedStudentRecord stores a *denormalized snapshot* (identity columns plus a
frozen JSON payload) instead of pointing at the live rows: once the snapshot is
sealed it no longer depends on anything that can be cascaded away.

Sealed records are append-only. `save()` raises on any edit to a sealed row and
`delete()` always raises, following FinanceLedgerLog's enforcement style
(finance/models.py) - the ledger there protects money, this protects a
permanent student record.
"""
import uuid

from django.db import models


class ArchiveProtectedError(Exception):
    """Raised when something tries to modify or remove a sealed archive row."""


class ArchivedStudentRecord(models.Model):
    """One permanently retained student history.

    A row exists for every student ever archived. While the source student is
    still on the system the snapshot is refreshable (so the archive stays
    current); the moment the source is deleted the row is sealed and becomes
    immutable.
    """

    REASON_GRADUATED = "graduated"
    REASON_TRANSFERRED = "transferred"
    REASON_WITHDRAWN = "withdrawn"
    REASON_DELETED = "deleted"
    REASON_MANUAL = "manual"
    REASON_CHOICES = [
        (REASON_GRADUATED, "Graduated"),
        (REASON_TRANSFERRED, "Transferred"),
        (REASON_WITHDRAWN, "Withdrawn"),
        (REASON_DELETED, "Removed from active students"),
        (REASON_MANUAL, "Manually archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="archived_students",
        null=True,
        blank=True,
    )

    # Kept as a convenience link back to the live student; goes NULL the moment
    # that student is deleted, which is exactly when `is_sealed` flips True.
    source_student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.SET_NULL,
        related_name="archive_records",
        null=True,
        blank=True,
    )

    # Denormalized identity. These are what search and the list view read, so
    # the archive stays fully searchable after the source rows are gone.
    student_id = models.CharField(max_length=50, db_index=True)
    admission_number = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=5, blank=True)
    profile_picture_url = models.TextField(blank=True)

    # Denormalized filter columns. Stored by name rather than by FK because a
    # Class or AcademicYear row can itself be deleted long after a student
    # graduates, and the archive must still be filterable by "the class they
    # were actually in".
    last_class_name = models.CharField(max_length=160, blank=True, db_index=True)
    last_class_id = models.IntegerField(null=True, blank=True)
    last_academic_year = models.CharField(max_length=120, blank=True, db_index=True)
    admission_date = models.DateField(null=True, blank=True)
    graduation_year = models.CharField(max_length=20, blank=True, db_index=True)

    archive_reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_MANUAL)
    archive_note = models.TextField(blank=True)

    # The complete frozen history - every section the archive page renders.
    # Built by alumni.services.build_student_archive_payload().
    snapshot = models.JSONField(default=dict, blank=True)
    snapshot_version = models.PositiveIntegerField(default=1)

    # True once the source student no longer exists. A sealed row can never be
    # rewritten or deleted.
    is_sealed = models.BooleanField(default=False, db_index=True)
    sealed_at = models.DateTimeField(null=True, blank=True)

    archived_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="archived_student_records",
        null=True,
        blank=True,
    )
    archived_at = models.DateTimeField(auto_now_add=True)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-archived_at"]
        verbose_name = "archived student record"
        verbose_name_plural = "archived student records"
        indexes = [
            models.Index(fields=["tenant", "last_academic_year"], name="alumni_asr_year_idx"),
            models.Index(fields=["tenant", "last_class_name"], name="alumni_asr_class_idx"),
            models.Index(fields=["tenant", "student_id"], name="alumni_asr_stuid_idx"),
            models.Index(fields=["tenant", "is_sealed"], name="alumni_asr_sealed_idx"),
        ]

    def __str__(self):
        return f"Archive({self.student_id} - {self.full_name})"

    def save(self, *args, **kwargs):
        if self.is_sealed and not self._state.adding:
            # The write that *performs* the sealing is allowed through - the row
            # in the database is still unsealed at that point. Every write after
            # it finds is_sealed already True and is rejected.
            already_sealed = type(self).objects.filter(pk=self.pk).values_list("is_sealed", flat=True).first()
            if already_sealed:
                raise ArchiveProtectedError(
                    "Archived student records are permanent and cannot be modified once sealed."
                )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ArchiveProtectedError("Archived student records are permanent and cannot be deleted.")
