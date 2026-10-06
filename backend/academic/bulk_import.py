"""Shared logic for adding templates to the central lesson-plan resource bank -
used by the import_lesson_resources management command. Mirrors
exams/bulk_import.py's central question bank pattern.
"""
from django.core.files import File

from tenants.models import Tenant

from .models import LessonPlanResource, Subject

# Same global (non-school) tenant used for every lesson-resource template -
# never a real school's tenant, since every school's own Subject rows are
# separate database rows even for the "same" subject name.
GLOBAL_TENANT_SLUG = "schooldom-global-lesson-bank"
GLOBAL_TENANT_NAME = "SchoolDom Global Lesson Resource Bank"


def import_lesson_resource(
    *,
    subject_name,
    title,
    grade_level="",
    description="",
    objectives="",
    activities="",
    resources="",
    assessment="",
    attachment_path=None,
):
    """Creates or updates one LessonPlanResource in the global bank, matched by
    (subject, title). Safe to re-run: re-importing the same subject+title
    updates the existing row instead of duplicating it. attachment_path, if
    given, must be a real file path on disk - its contents are copied in."""
    tenant, _ = Tenant.objects.get_or_create(slug=GLOBAL_TENANT_SLUG, defaults={"name": GLOBAL_TENANT_NAME})

    subject = Subject.objects.filter(tenant=tenant, name__iexact=subject_name).first()
    if not subject:
        subject = Subject.objects.create(tenant=tenant, name=subject_name, code=subject_name[:20])

    resource, created = LessonPlanResource.objects.get_or_create(
        tenant=tenant,
        subject=subject,
        title=title,
        defaults={
            "grade_level": grade_level,
            "description": description,
            "objectives": objectives,
            "activities": activities,
            "resources": resources,
            "assessment": assessment,
        },
    )
    if not created:
        resource.grade_level = grade_level
        resource.description = description
        resource.objectives = objectives
        resource.activities = activities
        resource.resources = resources
        resource.assessment = assessment

    if attachment_path:
        with open(attachment_path, "rb") as handle:
            resource.attachment.save(attachment_path.name, File(handle), save=False)

    resource.save()
    return resource, created
