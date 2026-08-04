"""Alumni / Student Archive API - read-only by design.

Every endpoint here is GET. The archive never edits a student record; the only
row this app ever writes is its own snapshot, and that happens automatically in
alumni.signals when a student is deleted (see that module for why it has to run
in pre_delete).

A student appears in exactly one of two ways:
  * still on the system -> read live, so the archive is never stale
  * deleted             -> read from the sealed snapshot
Both render through the same payload shape, so the page cannot tell them apart.
"""
from django.db.models import Q
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


def _active_students(user):
    return StudentProfile.objects.filter(user__tenant=user.tenant).select_related(
        "user", "current_class", "current_term__academic_year"
    )


def _archived_records(user):
    return ArchivedStudentRecord.objects.filter(tenant=user.tenant)


def _active_student_row(student_profile, request=None):
    from users.app_views import _class_label, _profile_picture_url

    student_user = student_profile.user
    academic_year = ""
    if student_profile.current_term_id and student_profile.current_term.academic_year_id:
        academic_year = student_profile.current_term.academic_year.name

    return {
        "key": f"active:{student_profile.id}",
        "record_id": str(student_profile.id),
        "student_id": student_profile.student_id,
        "admission_number": student_profile.admission_number,
        "name": student_user.get_full_name(),
        "email": student_user.email,
        "gender": student_user.gender or "",
        "profile_picture": _profile_picture_url(request, student_user),
        "class_name": _class_label(student_profile.current_class) if student_profile.current_class_id else "",
        "academic_year": academic_year,
        "admission_date": student_profile.admission_date.isoformat() if student_profile.admission_date else None,
        "graduation_year": "",
        "archive_reason": "",
        "archive_reason_display": "",
        "archived_at": None,
        "is_sealed": False,
        "is_active_student": True,
        "status": "Active" if student_user.is_active else "Inactive",
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_overview(request):
    """Filter options and counts - the payload the screen loads with."""
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    active = _active_students(user)
    archived = _archived_records(user)

    # Academic years and classes are offered from both sides, so a session or
    # class that only exists in the archive (because the live row was later
    # deleted) is still selectable.
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

    return Response(
        {
            "success": True,
            "summary": {
                "active_students": active.count(),
                "archived_students": archived.count(),
                "sealed_records": archived.filter(is_sealed=True).count(),
                "total_records": active.count() + archived.filter(source_student__isnull=True).count(),
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
    """Merged list of active students and archived records."""
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    search = str(request.query_params.get("search") or "").strip()
    class_name = str(request.query_params.get("class_name") or "").strip()
    class_id = str(request.query_params.get("class_id") or "").strip()
    academic_year = str(request.query_params.get("academic_year") or "").strip()
    scope = str(request.query_params.get("scope") or "all").strip().lower()

    rows = []

    if scope in {"all", "active"}:
        active = _active_students(user)
        if class_id.isdigit():
            active = active.filter(current_class_id=int(class_id))
        if academic_year:
            active = active.filter(current_term__academic_year__name=academic_year)
        if search:
            active = active.filter(
                Q(student_id__icontains=search)
                | Q(admission_number__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__email__icontains=search)
            )
        for student_profile in active[:LIST_CAP]:
            row = _active_student_row(student_profile, request=request)
            # A class filter given by name (an archive-only class) still has to
            # match live students whose class carries that same label.
            if class_name and row["class_name"] != class_name:
                continue
            rows.append(row)

    if scope in {"all", "archived"}:
        archived = _archived_records(user)
        # An unsealed record still has its live student in the list above -
        # showing both would duplicate the student.
        if scope == "all":
            archived = archived.filter(source_student__isnull=True)
        if class_name:
            archived = archived.filter(last_class_name=class_name)
        if class_id.isdigit():
            archived = archived.filter(last_class_id=int(class_id))
        if academic_year:
            archived = archived.filter(last_academic_year=academic_year)
        if search:
            archived = archived.filter(
                Q(student_id__icontains=search)
                | Q(admission_number__icontains=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
            )
        rows.extend(archived_record_payload(record) for record in archived[:LIST_CAP])

    rows.sort(key=lambda row: (row.get("name") or "").lower())
    return Response({"success": True, "count": len(rows), "students": rows})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_student_detail(request, student_key):
    """One student's complete history.

    `student_key` is "active:<profile-id>" or "archived:<record-id>" - the key
    the list hands back, so the caller never has to know which side a student
    lives on.
    """
    denied = _require_admin(request)
    if denied:
        return denied

    user = request.user
    kind, _, identifier = str(student_key).partition(":")

    if kind == "archived":
        record = get_object_or_404(_archived_records(user), id=identifier)
        payload = dict(record.snapshot or {})
        payload["archive"] = archived_record_payload(record)
        payload["is_live"] = False
        return Response({"success": True, "student": payload})

    if kind == "active":
        student_profile = get_object_or_404(_active_students(user), id=identifier)
    else:
        # Bare value - accept a student ID or admission number so the page can
        # be linked to directly from elsewhere.
        student_profile = (
            _active_students(user)
            .filter(Q(student_id__iexact=student_key) | Q(admission_number__iexact=student_key))
            .first()
        )
        if student_profile is None:
            record = (
                _archived_records(user)
                .filter(Q(student_id__iexact=student_key) | Q(admission_number__iexact=student_key))
                .first()
            )
            if record is None:
                return Response(
                    {"success": False, "message": "No student found for that ID."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            payload = dict(record.snapshot or {})
            payload["archive"] = archived_record_payload(record)
            payload["is_live"] = False
            return Response({"success": True, "student": payload})

    payload = build_student_archive_payload(student_profile, request=request)
    payload["archive"] = _active_student_row(student_profile, request=request)
    payload["is_live"] = True
    return Response({"success": True, "student": payload})
