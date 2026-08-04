"""Alumni / Student Archive API - read-only by design.

Every endpoint here is GET. The archive never edits a student record; the only
row this app ever writes is its own snapshot, and that happens automatically in
alumni.signals when a student is deleted (see that module for why it has to run
in pre_delete).

Only former students appear here. A student currently enrolled belongs on the
Students screen, not in the archive - they enter this module by being graduated
(promoted to Alumni), transferred, withdrawn, or deleted.

A record is read in one of two ways:
  * source student still in the database -> read live, so it is never stale
  * source student gone                  -> read from the sealed snapshot
Both render through the same payload shape, so the page cannot tell them apart.
"""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import StudentProfile

from .models import ArchivedStudentRecord
from .services import archived_record_payload, build_student_archive_payload

ADMIN_ROLES = {"school_admin", "principal", "super_admin", "school_superadmin"}
LIST_CAP = 1000


def _require_admin(request):
    if request.user.role not in ADMIN_ROLES:
        return Response(
            {"success": False, "message": "Only administrators can view the student archive."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _archived_records(user):
    return ArchivedStudentRecord.objects.filter(tenant=user.tenant)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_overview(request):
    """Filter options and counts - the payload the screen loads with."""
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    archived = _archived_records(user)

    # Sessions and classes are offered from both the school's live records and
    # the archive's own denormalized columns, so a session or class that has
    # since been deleted is still selectable for the alumni who left from it.
    from academic.models import AcademicYear, Class
    from users.app_views import _class_label, _tenant_for_model

    academic_years = []
    legacy_tenant = _tenant_for_model(AcademicYear, user)
    if legacy_tenant:
        academic_years = [
            {"id": year.id, "name": year.name, "is_current": getattr(year, "is_current", False)}
            for year in AcademicYear.objects.filter(tenant=legacy_tenant).order_by("-start_date")
        ]
    known_years = {year["name"] for year in academic_years}
    for name in archived.exclude(last_academic_year="").values_list("last_academic_year", flat=True).distinct():
        if name and name not in known_years:
            known_years.add(name)
            academic_years.append({"id": None, "name": name, "is_current": False})

    classes = []
    class_tenant = _tenant_for_model(Class, user)
    if class_tenant:
        classes = [
            {"id": item.id, "name": _class_label(item)}
            for item in Class.objects.filter(tenant=class_tenant).order_by("name", "section")
        ]
    known_classes = {item["name"] for item in classes}
    for name in archived.exclude(last_class_name="").values_list("last_class_name", flat=True).distinct():
        if name and name not in known_classes:
            known_classes.add(name)
            classes.append({"id": None, "name": name})

    reason_counts = {value: 0 for value, _ in ArchivedStudentRecord.REASON_CHOICES}
    for row in archived.values("archive_reason").annotate(total=Count("id")):
        reason_counts[row["archive_reason"]] = row["total"]

    return Response(
        {
            "success": True,
            "summary": {
                "total_alumni": archived.count(),
                "graduated": reason_counts.get(ArchivedStudentRecord.REASON_GRADUATED, 0),
                "transferred": reason_counts.get(ArchivedStudentRecord.REASON_TRANSFERRED, 0),
                "sealed_records": archived.filter(is_sealed=True).count(),
            },
            "academic_years": academic_years,
            "classes": sorted(classes, key=lambda item: item["name"]),
            "archive_reasons": [
                {"value": value, "label": label} for value, label in ArchivedStudentRecord.REASON_CHOICES
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_students(request):
    """Former students only.

    Currently enrolled students are deliberately absent: this is the archive of
    people who have left, and a student who is still on the roll is managed from
    the Students screen instead.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    search = str(request.query_params.get("search") or "").strip()
    class_name = str(request.query_params.get("class_name") or "").strip()
    class_id = str(request.query_params.get("class_id") or "").strip()
    academic_year = str(request.query_params.get("academic_year") or "").strip()
    reason = str(request.query_params.get("reason") or "").strip()

    archived = _archived_records(user)
    if class_name:
        archived = archived.filter(last_class_name=class_name)
    if class_id.isdigit():
        archived = archived.filter(last_class_id=int(class_id))
    if academic_year:
        archived = archived.filter(last_academic_year=academic_year)
    if reason:
        archived = archived.filter(archive_reason=reason)
    if search:
        archived = archived.filter(
            Q(student_id__icontains=search)
            | Q(admission_number__icontains=search)
            | Q(full_name__icontains=search)
            | Q(email__icontains=search)
        )

    rows = [archived_record_payload(record) for record in archived[:LIST_CAP]]
    rows.sort(key=lambda row: (row.get("name") or "").lower())
    return Response({"success": True, "count": len(rows), "students": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_student_detail(request, student_key):
    """One former student's complete history.

    `student_key` is "archived:<record-id>" - the key the list hands back - or a
    bare Student ID / admission number so the page can be linked to directly.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    kind, _, identifier = str(student_key).partition(":")

    if kind == "archived":
        record = get_object_or_404(_archived_records(user), id=identifier)
    else:
        record = (
            _archived_records(user)
            .filter(Q(student_id__iexact=student_key) | Q(admission_number__iexact=student_key))
            .first()
        )
        if record is None:
            return Response(
                {"success": False, "message": "No alumni record found for that ID."},
                status=status.HTTP_404_NOT_FOUND,
            )

    # A graduate's rows are still in the database until they are deleted, so
    # read them live and keep the page accurate; the frozen snapshot is the
    # fallback for once those rows are gone.
    if record.source_student_id:
        student_profile = (
            StudentProfile.objects.select_related("user", "current_class", "current_term__academic_year")
            .filter(pk=record.source_student_id)
            .first()
        )
        if student_profile is not None:
            payload = build_student_archive_payload(student_profile, request=request)
            payload["archive"] = archived_record_payload(record)
            payload["is_live"] = True
            return Response({"success": True, "student": payload})

    payload = dict(record.snapshot or {})
    payload["archive"] = archived_record_payload(record)
    payload["is_live"] = False
    return Response({"success": True, "student": payload})
