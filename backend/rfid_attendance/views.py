"""
Endpoints consumed by the SchoolDom.Rfid.Win7 desktop app only. Authentication is
the same JWT login every other SchoolDom client uses (POST /api/auth/login/) -
there is no separate device-pairing token, matching the decision to drop QR
pairing from this feature's scope. Whoever is signed into the desktop app acts
as the "operator" for both card assignment and attendance scans.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academic.models import AttendanceRecord, Class
from users.models import StudentProfile, User
from users.app_views import (
    AttendanceClockError,
    _attendance_clock_payload,
    _attendance_location_payload,
    _class_label,
    _record_attendance_clock,
    _resolve_school_tenant_for_user,
    _tenant_for_model,
)

from .models import CardAssignment
from .serializers import CardAssignmentSerializer

# Card assignment is admin-only ("built strictly into the desktop app", spec
# Section 4) - a teacher/staff member can still operate the reader for
# attendance scans, but cannot create/revoke the card-to-student mapping.
ADMIN_ROLES = {'school_admin', 'principal', 'super_admin', 'school_superadmin'}
SCAN_OPERATOR_ROLES = ADMIN_ROLES | {'teacher', 'staff'}


def _forbidden(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_403_FORBIDDEN)


def _bad_request(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _require_school(user):
    school = _resolve_school_tenant_for_user(user)
    if not school:
        return None, _bad_request('Your account is not linked to a school.')
    return school, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def card_assignments_pull(request):
    """Full active-assignment snapshot for the desktop app's local cache
    (Section 1d/4e) - pulled on login and periodically thereafter so a scan can
    still be matched locally even if the network drops right after."""
    if request.user.role not in SCAN_OPERATOR_ROLES:
        return _forbidden('Only school staff can sync card assignments.')

    school, error = _require_school(request.user)
    if error:
        return error

    assignments = CardAssignment.objects.select_related('student').filter(
        tenant=school, status='active',
    ).order_by('student__first_name', 'student__last_name')
    return Response({
        'success': True,
        'data': CardAssignmentSerializer(assignments, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_assignment_create(request):
    """Section 4b/4c/4d - assign a card to a student. `force=true` is how the
    desktop app confirms a reassignment after showing the admin both student
    names (Section 4d); without it, a conflict is reported, never silently
    overwritten."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    card_uid = str(request.data.get('card_uid') or '').strip()
    student_id = str(request.data.get('student_id') or '').strip()
    force = bool(request.data.get('force'))
    if not card_uid or not student_id:
        return _bad_request('card_uid and student_id are required.')

    try:
        student = User.objects.get(id=student_id, tenant=school, role='student')
    except (User.DoesNotExist, ValueError):
        return Response(
            {'success': False, 'message': 'Student not found at this school.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    with transaction.atomic():
        card_conflict = CardAssignment.objects.select_for_update().filter(
            tenant=school, card_uid=card_uid, status='active',
        ).exclude(student=student).select_related('student').first()
        student_conflict = CardAssignment.objects.select_for_update().filter(
            tenant=school, student=student, status='active',
        ).exclude(card_uid=card_uid).first()

        if (card_conflict or student_conflict) and not force:
            return Response(
                {
                    'success': False,
                    'conflict': True,
                    'message': (
                        f'Card {card_uid} is already assigned to {card_conflict.student.get_full_name()}.'
                        if card_conflict
                        else f'{student.get_full_name()} already has an active card ({student_conflict.card_uid}).'
                    ),
                    'conflicting_student_name': card_conflict.student.get_full_name() if card_conflict else None,
                    'conflicting_card_uid': student_conflict.card_uid if student_conflict else None,
                },
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        if card_conflict:
            card_conflict.status = 'revoked'
            card_conflict.revoked_at = now
            card_conflict.revoked_by = request.user
            card_conflict.save(update_fields=['status', 'revoked_at', 'revoked_by'])
        if student_conflict:
            student_conflict.status = 'revoked'
            student_conflict.revoked_at = now
            student_conflict.revoked_by = request.user
            student_conflict.save(update_fields=['status', 'revoked_at', 'revoked_by'])

        assignment = CardAssignment.objects.create(
            tenant=school,
            student=student,
            card_uid=card_uid,
            status='active',
            assigned_by=request.user,
        )

    return Response(
        {'success': True, 'message': 'Card assigned.', 'data': CardAssignmentSerializer(assignment).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_assignment_revoke(request):
    """Section 4d - unassign. The row is kept (status=revoked) for audit
    history, never hard-deleted."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can revoke RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    card_uid = str(request.data.get('card_uid') or '').strip()
    student_id = str(request.data.get('student_id') or '').strip()
    if not card_uid and not student_id:
        return _bad_request('card_uid or student_id is required.')

    query = CardAssignment.objects.filter(tenant=school, status='active')
    if card_uid:
        query = query.filter(card_uid=card_uid)
    if student_id:
        query = query.filter(student_id=student_id)
    assignment = query.first()
    if not assignment:
        return Response(
            {'success': False, 'message': 'No active assignment found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    assignment.status = 'revoked'
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = request.user
    assignment.save(update_fields=['status', 'revoked_at', 'revoked_by'])
    return Response({'success': True, 'message': 'Card unassigned.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def attendance_scan_create(request):
    """Section 3 - one flushed queue entry from the desktop app's offline
    queue. Idempotent on idempotency_key: a retried POST for a scan that
    already made it to the server returns the original result instead of
    toggling clock_in -> clock_out a second time."""
    if request.user.role not in SCAN_OPERATOR_ROLES:
        return _forbidden('Only school staff can record RFID attendance.')

    school, error = _require_school(request.user)
    if error:
        return error

    card_uid = str(request.data.get('card_uid') or '').strip()
    idempotency_key = str(request.data.get('idempotency_key') or '').strip()
    if not card_uid or not idempotency_key:
        return _bad_request('card_uid and idempotency_key are required.')

    existing = AttendanceRecord.objects.filter(idempotency_key=idempotency_key).select_related('student').first()
    if existing:
        return Response({
            'success': True,
            'message': 'Already recorded (retry of a previous scan).',
            'duplicate': True,
            'attendance': {
                'status': existing.status,
                'date': existing.date,
                **_attendance_clock_payload(existing),
            },
        })

    assignment = CardAssignment.objects.select_related('student').filter(
        tenant=school, card_uid=card_uid, status='active',
    ).first()
    if not assignment:
        return Response(
            {'success': False, 'unregistered': True, 'message': f'Card {card_uid} is not linked to any student.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    student = assignment.student
    student_profile = StudentProfile.objects.select_related('current_class').filter(user=student).first()

    tenant_obj = _tenant_for_model(AttendanceRecord, request.user)
    if not tenant_obj:
        return _bad_request('Unable to resolve school attendance records.')

    try:
        location = _attendance_location_payload(request, require_location=False)
    except ValueError as exc:
        return _bad_request(str(exc))

    try:
        attendance, action, message = _record_attendance_clock(
            student_user=student,
            student_profile=student_profile,
            tenant_obj=tenant_obj,
            actor=request.user,
            location=location,
            attendance_date=timezone.localdate(),
            school_name=school.name,
        )
    except AttendanceClockError as exc:
        return _bad_request(str(exc))

    AttendanceRecord.objects.filter(pk=attendance.pk).update(
        idempotency_key=idempotency_key,
        card_uid=card_uid,
    )

    return Response({
        'success': True,
        'message': message,
        'action': action,
        'student': {'id': str(student.id), 'name': student.get_full_name()},
        'attendance': {
            'status': attendance.status,
            'date': attendance.date,
            **_attendance_clock_payload(attendance),
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def classes_lookup(request):
    """Feeds the desktop app's class picker for Section 4c (Bulk Assign Cards)."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    classes = Class.objects.filter(studentprofile__user__tenant=school).distinct().order_by('name', 'section')
    return Response({
        'success': True,
        'data': [{'id': c.id, 'label': _class_label(c)} for c in classes],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def students_lookup(request):
    """Feeds the desktop app's student picker for Section 4b/4c - search by
    name/ID, optionally scoped to one class, optionally excluding students who
    already have an active card (used by Bulk Assign to default to the next
    unassigned student)."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    qs = StudentProfile.objects.select_related('user', 'current_class').filter(user__tenant=school)

    class_id = str(request.query_params.get('class_id') or '').strip()
    if class_id:
        qs = qs.filter(current_class_id=class_id)

    search = str(request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(student_id__icontains=search)
        )

    active_card_student_ids = set(
        CardAssignment.objects.filter(tenant=school, status='active').values_list('student_id', flat=True)
    )
    exclude_assigned = str(request.query_params.get('exclude_assigned') or '').lower() == 'true'

    results = []
    for profile in qs.order_by('user__first_name', 'user__last_name')[:300]:
        has_card = profile.user_id in active_card_student_ids
        if exclude_assigned and has_card:
            continue
        results.append({
            'id': str(profile.user_id),
            'name': profile.user.get_full_name() or profile.user.email,
            'student_id': profile.student_id,
            'class_name': _class_label(profile.current_class) if profile.current_class else None,
            'has_active_card': has_card,
        })

    return Response({'success': True, 'data': results})
