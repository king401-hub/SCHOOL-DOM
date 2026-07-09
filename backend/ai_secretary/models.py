"""Student attendance model — managed by AI Secretary, separate from teacher attendance."""
import uuid
from django.db import models


class StudentAttendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="student_attendances",
        limit_choices_to={"role": "student"},
    )
    tenant = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="student_attendances",
    )
    date = models.DateField()
    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("late", "Late"),
        ("excused", "Excused"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_student_attendances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "date", "tenant")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["tenant", "date"]),
            models.Index(fields=["student", "date"]),
        ]

    def __str__(self):
        return f"{self.student} — {self.date} — {self.status}"
