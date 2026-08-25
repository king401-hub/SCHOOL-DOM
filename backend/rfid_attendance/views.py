"""
Endpoints consumed by the SchoolDom.Rfid.Win7 desktop app only. Authentication is
the same JWT login every other SchoolDom client uses (POST /api/auth/login/) -
there is no separate device-pairing token, matching the decision to drop QR
pairing from this feature's scope. Whoever is signed into the desktop app acts
as the "operator" for both card assignment and attendance scans.

A card can be assigned to any tenant user, not just students - teachers and
admins can badge themselves in too. Where the resulting attendance record
lands depends on the holder's role: students go to academic.AttendanceRecord
(GPS-aware, used by the rest of the student attendance system), everyone else
goes to attendance.TeacherAttendance (no GPS - an RFID desktop scan has no
location to offer, unlike the phone-based QR self-scan that model was
originally built for).
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academic.models import AttendanceRecord, Class
from attendance.models import TeacherAttendance
from attendance.views import _apply_clock_out, get_client_ip
from users.models import StudentProfile, User
from users.app_views import (
    AttendanceClockError,
    _attendance_clock_payload,
    _attendance_location_payload,
    _class_label,
    _profile_picture_url,
    _record_attendance_clock,
    _resolve_school_tenant_for_user,
    _tenant_for_model,
)

from .models import CardAssignment
from .serializers import CardAssignmentSerializer

# Card assignment is admin-only ("built strictly into the desktop app", spec
# Section 4) - a teacher/staff member can still operate the reader for
# attendance scans, but cannot create/revoke the card-to-person mapping.
ADMIN_ROLES = {'school_admin', 'principal', 'super_admin', 'school_superadmin'}
SCAN_OPERATOR_ROLES = ADMIN_ROLES | {'teacher', 'staff'}
# Default set the "assign a card" picker searches across when no explicit
# ?roles= filter is given - deliberately excludes 'parent': a parent picking
# a child up at the gate isn't what this feature is for.
ASSIGNABLE_ROLES = SCAN_OPERATOR_ROLES | {'student'}
# A clock-in followed immediately by a clock-out is almost always an
# accidental second tap, not someone actually leaving - require this much
# elapsed time before a scan is accepted as the clock-out half. Separate
# from ATTENDANCE_DOUBLE_SCAN_SECONDS (users/app_views.py, 120s) which
# guards the shared QR/GPS clock flow other clients use - this is an
# RFID-specific, longer rule layered on top, not a replacement for it.
MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT = 3600


def _person_summary(request, user_obj):
    """Name/role/photo/class for one person - used both by the card-assignment
    conflict response (Section 4d: "show the already-assigned person's name,
    picture, and class") and anywhere else a rich person card is useful."""
    if not user_obj:
        return None
    profile = StudentProfile.objects.select_related('current_class').filter(user=user_obj).first()
    return {
        'id': str(user_obj.id),
        'name': user_obj.get_full_name() or user_obj.email,
        'role': user_obj.role,
        'role_label': user_obj.get_role_display(),
        'photo_url': _profile_picture_url(request, user_obj),
        'class_name': _class_label(profile.current_class) if profile and profile.current_class else None,
    }


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

    assignments = CardAssignment.objects.select_related('holder').filter(
        tenant=school, status='active',
    ).order_by('holder__first_name', 'holder__last_name')
    return Response({
        'success': True,
        'data': CardAssignmentSerializer(assignments, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_assignment_create(request):
    """Section 4b/4c/4d - assign a card to any person at this school (student,
    teacher, or admin - admins can assign themselves one too). `force=true` is
    how the desktop app confirms a reassignment after showing the admin both
    names (Section 4d); without it, a conflict is reported, never silently
    overwritten."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    card_uid = str(request.data.get('card_uid') or '').strip()
    person_id = str(request.data.get('person_id') or request.data.get('student_id') or '').strip()
    force = bool(request.data.get('force'))
    if not card_uid or not person_id:
        return _bad_request('card_uid and person_id are required.')

    try:
        person = User.objects.get(id=person_id, tenant=school)
    except (User.DoesNotExist, ValueError):
        return Response(
            {'success': False, 'message': 'Person not found at this school.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    with transaction.atomic():
        card_conflict = CardAssignment.objects.select_for_update().filter(
            tenant=school, card_uid=card_uid, status='active',
        ).exclude(holder=person).select_related('holder').first()
        person_conflict = CardAssignment.objects.select_for_update().filter(
            tenant=school, holder=person, status='active',
        ).exclude(card_uid=card_uid).first()

        if (card_conflict or person_conflict) and not force:
            return Response(
                {
                    'success': False,
                    'conflict': True,
                    'message': (
                        f'Card {card_uid} is already assigned to {card_conflict.holder.get_full_name()}.'
                        if card_conflict
                        else f'{person.get_full_name()} already has an active card ({person_conflict.card_uid}).'
                    ),
                    # Section 4d - "show the already-assigned person's name,
                    # picture, and class" so the admin can positively confirm
                    # they're revoking the right link before doing so.
                    'conflicting_person': _person_summary(request, card_conflict.holder) if card_conflict else None,
                    'conflicting_card_uid': person_conflict.card_uid if person_conflict else None,
                },
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        if card_conflict:
            card_conflict.status = 'revoked'
            card_conflict.revoked_at = now
            card_conflict.revoked_by = request.user
            card_conflict.save(update_fields=['status', 'revoked_at', 'revoked_by'])
        if person_conflict:
            person_conflict.status = 'revoked'
            person_conflict.revoked_at = now
            person_conflict.revoked_by = request.user
            person_conflict.save(update_fields=['status', 'revoked_at', 'revoked_by'])

        assignment = CardAssignment.objects.create(
            tenant=school,
            holder=person,
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
    person_id = str(request.data.get('person_id') or request.data.get('student_id') or '').strip()
    if not card_uid and not person_id:
        return _bad_request('card_uid or person_id is required.')

    query = CardAssignment.objects.filter(tenant=school, status='active')
    if card_uid:
        query = query.filter(card_uid=card_uid)
    if person_id:
        query = query.filter(holder_id=person_id)
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


def _find_by_idempotency_key(idempotency_key):
    """Checks both attendance tables - a retried sync POST doesn't know (or
    care) which one its own scan landed in last time."""
    student_record = AttendanceRecord.objects.filter(idempotency_key=idempotency_key).first()
    if student_record:
        return 'student', student_record
    staff_record = TeacherAttendance.objects.filter(idempotency_key=idempotency_key).first()
    if staff_record:
        return 'staff', staff_record
    return None, None


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

    kind, existing = _find_by_idempotency_key(idempotency_key)
    if existing:
        payload = (
            {'status': existing.status, 'date': existing.date, **_attendance_clock_payload(existing)}
            if kind == 'student'
            else {'status': existing.status, 'check_in_time': existing.check_in_time, 'check_out_time': existing.check_out_time}
        )
        return Response({
            'success': True,
            'message': 'Already recorded (retry of a previous scan).',
            'duplicate': True,
            'attendance': payload,
        })

    assignment = CardAssignment.objects.select_related('holder').filter(
        tenant=school, card_uid=card_uid, status='active',
    ).first()
    if not assignment:
        return Response(
            {'success': False, 'unregistered': True, 'message': f'Card {card_uid} is not linked to anyone.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    holder = assignment.holder

    if holder.role == 'student':
        return _record_student_scan(request, school, holder, card_uid, idempotency_key)
    return _record_staff_scan(request, school, holder, card_uid, idempotency_key)


def _too_soon_response(person, clocked_in_at):
    remaining = MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT - (timezone.now() - clocked_in_at).total_seconds()
    remaining_minutes = max(1, int(remaining // 60) + 1)
    return Response(
        {
            'success': False,
            'too_soon': True,
            'message': f'{person.get_full_name()} clocked in recently - wait {remaining_minutes} more minute(s) before clocking out.',
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _record_student_scan(request, school, student, card_uid, idempotency_key):
    today = timezone.localdate()
    existing_today = AttendanceRecord.objects.filter(student=student, date=today).first()
    if existing_today and existing_today.clock_in_at and not existing_today.clock_out_at:
        elapsed = (timezone.now() - existing_today.clock_in_at).total_seconds()
        if elapsed < MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT:
            return _too_soon_response(student, existing_today.clock_in_at)

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
        'person': {'id': str(student.id), 'name': student.get_full_name(), 'role': student.role},
        'attendance': {
            'status': attendance.status,
            'date': attendance.date,
            **_attendance_clock_payload(attendance),
        },
    }, status=status.HTTP_201_CREATED)


def _record_staff_scan(request, school, staff, card_uid, idempotency_key):
    """Teacher/admin path - attendance.TeacherAttendance, no GPS. An RFID
    desktop scan has no location to offer, unlike the phone-based QR
    self-scan (scan_qr_code) this model was originally built for - every
    location field below is left null on purpose, all of which are nullable
    on TeacherAttendance already."""
    today = timezone.localdate()
    existing = TeacherAttendance.objects.filter(teacher=staff, attendance_date=today).first()

    if existing is None:
        attendance = TeacherAttendance.objects.create(
            teacher=staff,
            tenant=school,
            status='present',
            ip_address=get_client_ip(request),
            device_info='SchoolDom RFID',
        )
        action = 'clock_in'
        message = f"{staff.get_full_name()} clocked in at {timezone.localtime(attendance.check_in_time).strftime('%I:%M %p').lstrip('0')}."
    elif existing.check_out_time is None:
        elapsed = (timezone.now() - existing.check_in_time).total_seconds()
        if elapsed < MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT:
            return _too_soon_response(staff, existing.check_in_time)

        no_location = {'latitude': None, 'longitude': None, 'accuracy': None, 'address': '', 'device_info': 'SchoolDom RFID'}
        _apply_clock_out(existing, no_location)
        attendance = existing
        action = 'clock_out'
        message = f"{staff.get_full_name()} clocked out at {timezone.localtime(attendance.check_out_time).strftime('%I:%M %p').lstrip('0')}."
    else:
        return _bad_request(f'{staff.get_full_name()} has already clocked out today.')

    TeacherAttendance.objects.filter(pk=attendance.pk).update(
        idempotency_key=idempotency_key,
        card_uid=card_uid,
    )

    return Response({
        'success': True,
        'message': message,
        'action': action,
        'person': {'id': str(staff.id), 'name': staff.get_full_name(), 'role': staff.role},
        'attendance': {
            'status': attendance.status,
            'check_in_time': attendance.check_in_time,
            'check_out_time': attendance.check_out_time,
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def classes_lookup(request):
    """Feeds the desktop app's class picker for Section 4c (Bulk Assign Cards) -
    students only, since "class" isn't a concept for staff."""
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
def people_lookup(request):
    """Feeds the desktop app's assign-a-card picker (Section 4b/4c) - search by
    name/email, optionally restricted to specific roles (?roles=teacher,staff;
    Bulk Assign passes roles=student), optionally scoped to one class (students
    only), optionally excluding people who already have an active card (used
    by Bulk Assign to default to the next unassigned student)."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user)
    if error:
        return error

    roles_param = str(request.query_params.get('roles') or '').strip()
    roles = {r.strip() for r in roles_param.split(',') if r.strip()} or ASSIGNABLE_ROLES

    qs = User.objects.filter(tenant=school, is_active=True, role__in=roles)

    class_id = str(request.query_params.get('class_id') or '').strip()
    if class_id:
        student_ids_in_class = StudentProfile.objects.filter(
            user__tenant=school, current_class_id=class_id,
        ).values_list('user_id', flat=True)
        qs = qs.filter(id__in=list(student_ids_in_class))

    search = str(request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
        )

    profiles_by_user_id = {
        p.user_id: p
        for p in StudentProfile.objects.filter(user__tenant=school).select_related('current_class')
    }
    active_card_holder_ids = set(
        CardAssignment.objects.filter(tenant=school, status='active').values_list('holder_id', flat=True)
    )
    exclude_assigned = str(request.query_params.get('exclude_assigned') or '').lower() == 'true'

    results = []
    for person in qs.order_by('first_name', 'last_name')[:300]:
        has_card = person.id in active_card_holder_ids
        if exclude_assigned and has_card:
            continue
        profile = profiles_by_user_id.get(person.id)
        results.append({
            'id': str(person.id),
            'name': person.get_full_name() or person.email,
            'role': person.role,
            'role_label': person.get_role_display(),
            'photo_url': _profile_picture_url(request, person),
            'student_id': profile.student_id if profile else None,
            'class_name': _class_label(profile.current_class) if profile and profile.current_class else None,
            'has_active_card': has_card,
        })

    return Response({'success': True, 'data': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_history(request):
    """Powers the desktop app's Attendance History screen - merges student
    (academic.AttendanceRecord) and staff (attendance.TeacherAttendance) rows
    that were captured via RFID (card_uid non-empty) into one list, newest
    first. ?date=YYYY-MM-DD filters to a single day; default is the last 7
    days so the screen isn't empty on a quiet week."""
    if request.user.role not in SCAN_OPERATOR_ROLES:
        return _forbidden('Only school staff can view attendance history.')

    school, error = _require_school(request.user)
    if error:
        return error

    date_str = str(request.query_params.get('date') or '').strip()
    if date_str:
        try:
            from datetime import datetime
            start_date = end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return _bad_request('date must be YYYY-MM-DD.')
    else:
        end_date = timezone.localdate()
        start_date = end_date - timezone.timedelta(days=7)

    student_rows = (
        AttendanceRecord.objects.select_related('student')
        .filter(student__tenant=school, date__gte=start_date, date__lte=end_date)
        .exclude(card_uid='')
        .order_by('-date', '-clock_in_at')[:200]
    )
    staff_rows = (
        TeacherAttendance.objects.select_related('teacher')
        .filter(tenant=school, attendance_date__gte=start_date, attendance_date__lte=end_date)
        .exclude(card_uid='')
        .order_by('-attendance_date', '-check_in_time')[:200]
    )

    entries = []
    for r in student_rows:
        entries.append({
            'person_name': r.student.get_full_name() or r.student.email,
            'role': 'student',
            'date': r.date,
            'clock_in_at': r.clock_in_at,
            'clock_out_at': r.clock_out_at,
            'status': r.status,
            'card_uid': r.card_uid,
        })
    for r in staff_rows:
        entries.append({
            'person_name': r.teacher.get_full_name() or r.teacher.email,
            'role': r.teacher.role,
            'date': r.attendance_date,
            'clock_in_at': r.check_in_time,
            'clock_out_at': r.check_out_time,
            'status': r.status,
            'card_uid': r.card_uid,
        })

    entries.sort(key=lambda e: e['clock_in_at'] or timezone.now(), reverse=True)

    return Response({'success': True, 'data': entries[:300]})
