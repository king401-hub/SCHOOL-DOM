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
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_time
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academic.models import AttendanceRecord, Class
from attendance.models import TeacherAttendance
from attendance.views import _apply_clock_out, get_client_ip
from core.schoolgate import require_full_product
from finance.services import fee_totals_by_student
from users.models import StudentProfile, User
from users.app_views import (
    AttendanceClockError,
    _attendance_clock_payload,
    _attendance_location_payload,
    _class_label,
    _profile_picture_url,
    _record_attendance_clock,
    _resolve_school_tenant_for_user,
    _send_attendance_sms_batch,
    _tenant_for_model,
)

from .models import CardAssignment, GateSettings
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
MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT = 3 * 3600


def get_or_create_gate_settings(tenant):
    """Lazily creates a GateSettings row (with the spec's example defaults)
    the first time any SchoolGate terminal at this school asks for its
    settings, rather than requiring a migration data-fixture per school."""
    settings_obj, _created = GateSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


def _gate_settings_payload(gate_settings):
    return {
        'mode': gate_settings.mode,
        'early_start': gate_settings.early_start,
        'early_end': gate_settings.early_end,
        'late_start': gate_settings.late_start,
        'late_end': gate_settings.late_end,
        'clockout_start': gate_settings.clockout_start,
        'clockout_end': gate_settings.clockout_end,
        'duplicate_protection_seconds': gate_settings.duplicate_protection_seconds,
        'has_pin': bool(gate_settings.admin_pin_hash),
    }


def _fees_payload_for_student(student_profile):
    # fee_totals_by_student's class_ids param feeds an `__in=` lookup, which
    # requires a real iterable (None raises TypeError) - matching how every
    # other caller builds it (finance/services.py's own admin snapshot).
    class_ids = [student_profile.current_class_id] if student_profile.current_class_id else []
    per_student, _fee_data = fee_totals_by_student([student_profile], class_ids)
    expected, paid = per_student.get(student_profile.id, (0, 0))
    outstanding = max(expected - paid, 0)
    return {'paid': str(paid), 'outstanding': str(outstanding)}


def _student_dva_payload(student_profile):
    """The spec's "Student DVA" - there's no per-student virtual account in
    the system, only a per-parent one (finance.ParentVirtualAccount). A
    student can have two linked parents with only one of them assigned a
    virtual account - checks every linked parent (not just .first(), which
    could silently pick the parent without one) and returns the first
    active account found. Falls back to the school's own account (from
    finance.AdminWallet) when no parent has one, so the gate/kiosk screen
    and printed receipt always have a real account to show rather than
    nothing at all."""
    parents = student_profile.parents.select_related('user__virtual_account').all()
    for parent in parents:
        account = getattr(getattr(parent, 'user', None), 'virtual_account', None)
        if account and account.is_active:
            return {
                'account_number': account.account_number,
                'bank_name': account.bank_name,
                'account_name': account.account_name,
            }

    from finance.models import AdminWallet
    admin_wallet = AdminWallet.objects.filter(tenant=student_profile.user.tenant).first()
    if admin_wallet:
        if admin_wallet.kuda_virtual_account_number:
            return {
                'account_number': admin_wallet.kuda_virtual_account_number,
                'bank_name': admin_wallet.kuda_virtual_account_bank_name,
                'account_name': admin_wallet.kuda_virtual_account_name,
            }
        if admin_wallet.bank_account_number:
            return {
                'account_number': admin_wallet.bank_account_number,
                'bank_name': admin_wallet.bank_code,
                'account_name': admin_wallet.bank_account_name,
            }
    return None


def _gate_sms_text(school, student, action, event, occurred_at=None):
    """Deliberately separate from users.app_views._attendance_sms_text -
    that one is gated behind a parent's paid Kids Monitor subscription
    (see _notify_parents_on_attendance); SchoolGate's parent SMS is
    unconditional and funded outside the school's SMS wallet (per product
    decision), and goes out via KudiSMS rather than the eBulkSMS that
    gated call site (and every other SMS in the platform) uses - see
    finance.services.send_kudisms.

    `occurred_at`: the real moment of the tap, for a scan replayed from a
    kiosk's offline queue - without this the text always said "now", so a
    scan that actually happened yesterday (queued while offline, synced
    this morning) read as if it had just happened. The date is always
    included (not just when it differs from today) so the message never
    depends on when the parent happens to read it.

    Signed with the school's own name, not "SchoolDom" - this message is
    the school talking to its own parents, not a platform notification."""
    moment = timezone.localtime(occurred_at or timezone.now())
    time_str = moment.strftime('%I:%M %p').lstrip('0')
    date_str = moment.strftime('%b %d')
    name = student.get_full_name() or student.email
    if action == 'clock_out':
        return f'{name} left school at {time_str} on {date_str}. -{school.name}'
    event_label = {'early': 'arrived (early)', 'late': 'arrived (late)'}.get(event, 'arrived')
    return f'{name} {event_label} at {time_str} on {date_str}. -{school.name}'


def _send_gate_sms(school, student_user, student_profile, action, event, occurred_at=None):
    from finance.services import guardian_contacts_for_student
    phone, _email = guardian_contacts_for_student(student_profile)
    if not phone:
        return
    message = _gate_sms_text(school, student_user, action, event, occurred_at=occurred_at)
    threading.Thread(
        target=_send_attendance_sms_batch,
        args=([(phone, message)], settings.SCHOOLGATE_SMS_PROVIDER),
        daemon=True,
    ).start()


def _send_gate_sms_from_wallet(school, student_user, student_profile, action, event, occurred_at=None):
    """SchoolGate Basic's version of _send_gate_sms: same message, same
    unconditional trigger (every scan, both directions), but billed to the
    school's own SMS wallet instead of funded free by SchoolDom - Basic's
    plan doesn't include the free daily clock-in/out SMS Premium gets, but
    the school can still send it themselves, the same way any other
    wallet-metered message in the platform works.

    Threaded like _send_gate_sms and for the same reason: this must never
    make the terminal wait on an SMS/wallet round-trip before it can show
    the scan result."""
    from finance.models import SmsMessageLog
    from finance.services import (
        InsufficientSmsCreditsError,
        SmsWalletLockedError,
        guardian_contacts_for_student,
        send_wallet_sms,
    )
    phone, _email = guardian_contacts_for_student(student_profile)
    if not phone:
        return
    message = _gate_sms_text(school, student_user, action, event, occurred_at=occurred_at)

    def _send():
        try:
            send_wallet_sms(
                school, phone, message,
                category=SmsMessageLog.ATTENDANCE,
                narration='SchoolGate attendance (Basic plan)',
            )
        except (InsufficientSmsCreditsError, SmsWalletLockedError):
            # An empty/locked wallet must never block attendance itself -
            # the scan is already recorded by the time this runs. The
            # parent simply doesn't get this one text; same reasoning every
            # other wallet-billed send in this codebase already follows.
            pass

    threading.Thread(target=_send, daemon=True).start()


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
        # SchoolGate spec sections 2A/2B - the human-readable student ID
        # (e.g. "STU/2024/001"), not user_obj.id (a UUID never shown to
        # anyone at the terminal). None for non-students.
        'student_id': profile.student_id if profile else None,
    }


def _forbidden(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_403_FORBIDDEN)


def _bad_request(message):
    return Response({'success': False, 'message': message}, status=status.HTTP_400_BAD_REQUEST)


def _require_school(user, school_code=''):
    # school_code lets a platform super_admin (who has no tenant of their own -
    # _resolve_school_tenant_for_user returns None for that role otherwise)
    # operate against an explicit school, e.g. the Superadmin Control Panel's
    # "Select School" step. Ignored/unnecessary for a normal school-level
    # admin, whose own tenant is used regardless.
    school = _resolve_school_tenant_for_user(user, school_code=school_code)
    if not school:
        message = (
            'Pick a school first.' if user.role == 'super_admin'
            else 'Your account is not linked to a school.'
        )
        return None, _bad_request(message)
    return school, None


def _school_code_from_request(request):
    return str(request.data.get('school_code') or request.query_params.get('school_code') or '').strip()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def card_assignments_pull(request):
    """Full active-assignment snapshot for the desktop app's local cache
    (Section 1d/4e) - pulled on login and periodically thereafter so a scan can
    still be matched locally even if the network drops right after."""
    if request.user.role not in SCAN_OPERATOR_ROLES:
        return _forbidden('Only school staff can sync card assignments.')

    school, error = _require_school(request.user, _school_code_from_request(request))
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

    school, error = _require_school(request.user, _school_code_from_request(request))
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

    # Only clears it if it's still this exact card - an admin who tapped
    # and assigned card A shouldn't wipe out a genuinely newer pending tap
    # of card B that arrived in the meantime.
    pending = cache.get(f'pending_card_scan:{school.schema_name}')
    if pending and pending.get('card_uid') == card_uid:
        cache.delete(f'pending_card_scan:{school.schema_name}')

    return Response(
        {'success': True, 'message': 'Card assigned.', 'data': CardAssignmentSerializer(assignment).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_card_scan(request):
    """Polled by the "Assign Student Card" wizard's tap-to-capture mode -
    the most recent card a kiosk/desktop app saw that wasn't linked to
    anyone yet (see the unregistered-card branch of attendance_scan_create
    above), so an admin can walk up to a terminal already in the field,
    tap the new card, and have its UID appear in the wizard instead of
    reading it off the terminal's screen and typing it in by hand.

    `since` (ISO datetime, required) scopes this to a tap that happened
    after the admin started waiting, so a stray unrelated tap from
    minutes earlier - e.g. a lost/expired card someone tried at the gate -
    is never mistaken for the one just made for this assignment.
    """
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can look up pending card scans.')

    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error

    since_raw = str(request.query_params.get('since') or '').strip()
    since = parse_datetime(since_raw) if since_raw else None
    if since_raw and not since:
        return _bad_request('since must be a valid ISO datetime.')

    entry = cache.get(f'pending_card_scan:{school.schema_name}')
    if not entry:
        return Response({'success': True, 'found': False})

    scanned_at = parse_datetime(entry.get('scanned_at') or '')
    if since and (not scanned_at or scanned_at < since):
        return Response({'success': True, 'found': False})

    return Response({
        'success': True,
        'found': True,
        'card_uid': entry.get('card_uid'),
        'scanned_at': entry.get('scanned_at'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def card_assignment_revoke(request):
    """Section 4d - unassign. The row is kept (status=revoked) for audit
    history, never hard-deleted."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can revoke RFID cards.')

    school, error = _require_school(request.user, _school_code_from_request(request))
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


# How far a client-reported scan time is trusted to be the real moment of
# the tap rather than something garbled/wrong. Backward: a terminal can
# genuinely sit offline for a long stretch (a bad SIM, a holiday) with scans
# queued the whole time - 30 days covers that without trusting an obviously
# broken clock. Forward: only small device clock drift, never a future scan.
SCANNED_AT_MAX_PAST = timedelta(days=30)
SCANNED_AT_MAX_FUTURE = timedelta(minutes=10)


def _parse_scanned_at(request):
    """The real moment a tap happened, when the client sent one and it looks
    sane - None otherwise, which every caller below treats exactly like it
    did before this field existed (fall back to timezone.now()).

    Exists because a kiosk that was offline queues the scan locally and
    replays it once back online, possibly a day or more later - without
    this, attendance recorded from a replay lands on the date/time the
    *replay* happened, not the date/time the student actually walked
    through the gate, and the parent SMS says the same wrong thing."""
    raw = str(request.data.get('scanned_at') or '').strip()
    if not raw:
        return None
    try:
        # parse_datetime doesn't itself guard against out-of-range components
        # (e.g. month=13) - it lets the underlying datetime() constructor
        # raise ValueError rather than returning None for those, unlike every
        # other malformed-string case. A corrupted/garbled client value must
        # never be able to 500 the whole scan - same reasoning as every other
        # "fall back to None" branch here.
        parsed = parse_datetime(raw)
    except (ValueError, TypeError):
        return None
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    now = timezone.now()
    if parsed < now - SCANNED_AT_MAX_PAST or parsed > now + SCANNED_AT_MAX_FUTURE:
        return None
    return parsed


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def attendance_scan_create(request):
    """Section 3 - one flushed queue entry from the desktop app's offline
    queue. Idempotent on idempotency_key: a retried POST for a scan that
    already made it to the server returns the original result instead of
    toggling clock_in -> clock_out a second time."""
    if request.user.role not in SCAN_OPERATOR_ROLES:
        return _forbidden('Only school staff can record RFID attendance.')

    locked = require_full_product(request.user)
    if locked:
        return locked

    school, error = _require_school(request.user, _school_code_from_request(request))
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
        # Remembered briefly so the "Assign Student Card" wizard's
        # tap-to-capture mode (see pending_card_scan below) can pick this
        # UID up on its own - an admin taps the new card on a terminal
        # already in the field exactly like a student would, instead of
        # reading the UID off its screen and typing it in by hand.
        cache.set(
            f'pending_card_scan:{school.schema_name}',
            {'card_uid': card_uid, 'scanned_at': timezone.now().isoformat()},
            timeout=120,
        )
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


def _too_early_response(gate_settings):
    # Deliberately avoids "already"/"wait"/"recently" - ScanHandler.kt's
    # looksLikeAlreadyHandled on the kiosk keys off exactly those words to
    # show "Already Recorded" instead of this message, which would be a
    # confusing title for "you're too early," not "you already scanned".
    opens_at = gate_settings.early_start.strftime('%I:%M %p').lstrip('0')
    return _bad_request(f"Clock-in opens at {opens_at}. Try again then.")


def _record_student_scan(request, school, student, card_uid, idempotency_key):
    scanned_at = _parse_scanned_at(request)
    today = timezone.localdate(scanned_at) if scanned_at else timezone.localdate()
    gate_settings = get_or_create_gate_settings(school)
    event = gate_settings.classify_event(timezone.localtime(scanned_at or timezone.now()).time())
    if event == 'too_early':
        return _too_early_response(gate_settings)

    existing_today = AttendanceRecord.objects.filter(student=student, date=today).first()
    # The blanket 3-hour "probably an accidental re-tap" rule doesn't apply
    # once the terminal's own configured clock-out window has opened - that
    # window is an explicit admin decision this scan should count as a
    # clock-out, not a heuristic that should get second-guessed by it. A
    # school whose clock-out window opens less than 3 hours after its
    # clock-in window closes (a shorter day, a half-day schedule) would
    # otherwise never be able to record a legitimate clock-out at all.
    if event != 'clockout' and existing_today and existing_today.clock_in_at and not existing_today.clock_out_at:
        elapsed = ((scanned_at or timezone.now()) - existing_today.clock_in_at).total_seconds()
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

    # Only the clock-out window forces a direction - a student with no
    # clock-in record yet still needs to be clocked OUT (not in, for the
    # first time, at 3pm) once the clock-out window opens, regardless of
    # whether they ever tapped in that morning. early/late/other are left
    # to _record_attendance_clock's own toggle inference (first tap today
    # -> clock_in, second -> clock_out): forcing clock_in here too would
    # let a student who already completed their whole day silently get a
    # fresh clock_in_at stamped over their finished record just by tapping
    # again during the morning window, instead of the "already clocked out
    # today" error that should stop them.
    requested_action = 'clock_out' if event == 'clockout' else ''

    try:
        attendance, action, message = _record_attendance_clock(
            student_user=student,
            student_profile=student_profile,
            tenant_obj=tenant_obj,
            actor=request.user,
            location=location,
            attendance_date=today,
            school_name=school.name,
            occurred_at=scanned_at,
            requested_action=requested_action,
            allow_clock_out_without_clock_in=(event == 'clockout'),
        )
    except AttendanceClockError as exc:
        return _bad_request(str(exc))

    AttendanceRecord.objects.filter(pk=attendance.pk).update(
        idempotency_key=idempotency_key,
        card_uid=card_uid,
    )

    # SchoolGate spec section 3: "No fee information should be displayed
    # during clock-out" - and section 2A (Attendance Only mode) never shows
    # fees at all, regardless of direction.
    fees = None
    student_dva = None
    if gate_settings.mode == GateSettings.MODE_FEE_TRACKER and action == 'clock_in' and student_profile:
        fees = _fees_payload_for_student(student_profile)
        student_dva = _student_dva_payload(student_profile)

    # Unconditional parent SMS on every scan (both directions) - a product
    # decision to send regardless of the paid Kids Monitor subscription
    # gate the phone/QR clock flow uses. Premium gets it free, funded by
    # SchoolDom and never charged to the school's SMS wallet (see
    # _send_gate_sms / _gate_sms_text docstrings). Basic doesn't include
    # that free send, but still gets the same text billed to its own SMS
    # wallet instead (see _send_gate_sms_from_wallet) - an empty/locked
    # wallet just means that one text doesn't go out, not that attendance
    # fails. Full-product schools are unaffected either way.
    # sms_sent_locally: the kiosk sends this text itself via the terminal's
    # own SIM when it couldn't reach us live, then replays the queued scan
    # once back online purely to persist the attendance record - skip
    # re-sending here or the parent gets the same SMS twice.
    sms_sent_locally = str(request.data.get('sms_sent_locally') or '').strip().lower() in ('1', 'true', 'yes')
    if not sms_sent_locally:
        if school.is_schoolgate and school.subscription_tier == "basic":
            _send_gate_sms_from_wallet(school, student, student_profile, action, event, occurred_at=scanned_at)
        else:
            _send_gate_sms(school, student, student_profile, action, event, occurred_at=scanned_at)

    return Response({
        'success': True,
        'message': message,
        'action': action,
        'attendance_event': event,
        'person': _person_summary(request, student),
        'fees': fees,
        'student_dva': student_dva,
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
    scanned_at = _parse_scanned_at(request)
    today = timezone.localdate(scanned_at) if scanned_at else timezone.localdate()
    gate_settings = get_or_create_gate_settings(school)
    event = gate_settings.classify_event(timezone.localtime(scanned_at or timezone.now()).time())
    if event == 'too_early':
        return _too_early_response(gate_settings)

    existing = TeacherAttendance.objects.filter(teacher=staff, attendance_date=today).first()
    # check_in_time is auto_now_add (create() always stamps the real current
    # time, ignoring any value passed in) and _apply_clock_out always sets
    # check_out_time to timezone.now() too (it's shared with the QR self-scan
    # path, which has no reason to ever backdate) - a replayed offline scan's
    # real timestamp can only land via a follow-up update(), same trick the
    # idempotency_key/card_uid write below already uses.
    extra_update = {}

    if existing is None:
        attendance = TeacherAttendance.objects.create(
            teacher=staff,
            tenant=school,
            status='present',
            ip_address=get_client_ip(request),
            device_info='SchoolDom RFID',
        )
        action = 'clock_in'
        event_time = scanned_at or attendance.check_in_time
        if scanned_at:
            extra_update['check_in_time'] = scanned_at
            extra_update['attendance_date'] = today
        local_event = timezone.localtime(event_time)
        message = f"{staff.get_full_name()} clocked in at {local_event.strftime('%I:%M %p').lstrip('0')} on {local_event.strftime('%b %d')}."
    elif existing.check_out_time is None:
        # Same override as _record_student_scan: once the terminal's own
        # configured clock-out window has opened, that's an explicit admin
        # decision this scan counts as a departure, not something the
        # unrelated 3-hour accidental-re-tap heuristic should second-guess.
        if event != 'clockout':
            elapsed = ((scanned_at or timezone.now()) - existing.check_in_time).total_seconds()
            if elapsed < MIN_SECONDS_BETWEEN_CLOCK_IN_AND_OUT:
                return _too_soon_response(staff, existing.check_in_time)

        no_location = {'latitude': None, 'longitude': None, 'accuracy': None, 'address': '', 'device_info': 'SchoolDom RFID'}
        _apply_clock_out(existing, no_location)
        attendance = existing
        action = 'clock_out'
        event_time = scanned_at or attendance.check_out_time
        if scanned_at:
            extra_update['check_out_time'] = scanned_at
        local_event = timezone.localtime(event_time)
        message = f"{staff.get_full_name()} clocked out at {local_event.strftime('%I:%M %p').lstrip('0')} on {local_event.strftime('%b %d')}."
    else:
        return _bad_request(f'{staff.get_full_name()} has already clocked out today.')

    TeacherAttendance.objects.filter(pk=attendance.pk).update(
        idempotency_key=idempotency_key,
        card_uid=card_uid,
        **extra_update,
    )
    if extra_update:
        attendance.refresh_from_db()

    return Response({
        'success': True,
        'message': message,
        'action': action,
        'person': _person_summary(request, staff),
        'attendance': {
            'status': attendance.status,
            'check_in_time': attendance.check_in_time,
            'check_out_time': attendance.check_out_time,
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gate_settings_get(request):
    """SchoolGate terminal's Settings screen (spec section 6) - operating
    mode, attendance windows, duplicate-protection interval. Never returns
    admin_pin_hash itself, only whether one has been set (has_pin)."""
    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error
    gate_settings = get_or_create_gate_settings(school)
    return Response({'success': True, 'data': _gate_settings_payload(gate_settings)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gate_settings_update(request):
    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error
    gate_settings = get_or_create_gate_settings(school)

    update_fields = []
    if 'mode' in request.data:
        mode = str(request.data.get('mode') or '').strip()
        if mode not in dict(GateSettings.MODE_CHOICES):
            return _bad_request('Invalid mode.')
        gate_settings.mode = mode
        update_fields.append('mode')

    time_fields = ['early_start', 'early_end', 'late_start', 'late_end', 'clockout_start', 'clockout_end']
    for field in time_fields:
        if field in request.data:
            parsed = parse_time(str(request.data.get(field) or ''))
            if not parsed:
                return _bad_request(f'{field} must be a valid HH:MM time.')
            setattr(gate_settings, field, parsed)
            update_fields.append(field)

    if 'duplicate_protection_seconds' in request.data:
        try:
            seconds = int(request.data.get('duplicate_protection_seconds'))
        except (TypeError, ValueError):
            return _bad_request('duplicate_protection_seconds must be a whole number.')
        if seconds < 0:
            return _bad_request('duplicate_protection_seconds cannot be negative.')
        gate_settings.duplicate_protection_seconds = seconds
        update_fields.append('duplicate_protection_seconds')

    if update_fields:
        gate_settings.save(update_fields=update_fields + ['updated_at'])
    return Response({'success': True, 'data': _gate_settings_payload(gate_settings)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gate_pin_verify(request):
    """No PIN configured yet is treated as open, not locked - a school
    shouldn't be locked out of Settings before ever setting one up."""
    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error
    gate_settings = get_or_create_gate_settings(school)
    pin = str(request.data.get('pin') or '')
    if not gate_settings.admin_pin_hash:
        return Response({'success': True, 'valid': True})
    return Response({'success': True, 'valid': check_password(pin, gate_settings.admin_pin_hash)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gate_pin_set(request):
    """Changing an existing PIN requires the current one; setting the very
    first PIN (admin_pin_hash blank) does not."""
    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error
    gate_settings = get_or_create_gate_settings(school)

    current_pin = str(request.data.get('current_pin') or '')
    new_pin = str(request.data.get('new_pin') or '').strip()
    if not new_pin:
        return _bad_request('new_pin is required.')
    if gate_settings.admin_pin_hash and not check_password(current_pin, gate_settings.admin_pin_hash):
        return Response({'success': False, 'message': 'Current PIN is incorrect.'}, status=status.HTTP_403_FORBIDDEN)

    gate_settings.admin_pin_hash = make_password(new_pin)
    gate_settings.save(update_fields=['admin_pin_hash', 'updated_at'])
    return Response({'success': True, 'message': 'PIN updated.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fee_reminder_send(request):
    """SchoolGate spec section 2B's "Send Fee Reminder" button - an
    on-demand SMS, distinct from the automatic per-scan attendance SMS
    (_send_gate_sms), sent the same unconditional, non-wallet, KudiSMS way."""
    school, error = _require_school(request.user, _school_code_from_request(request))
    if error:
        return error
    # student_id here is the User id, matching what _person_summary's
    # 'id' field (str(user_obj.id)) actually returns to the kiosk app -
    # not StudentProfile's own (different) primary key.
    student_id = request.data.get('student_id')
    student_profile = StudentProfile.objects.select_related('user').filter(
        user_id=student_id, user__tenant=school,
    ).first()
    if not student_profile:
        return Response({'success': False, 'message': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    from finance.services import guardian_contacts_for_student
    phone, _email = guardian_contacts_for_student(student_profile)
    if not phone:
        return _bad_request('No guardian phone number on file for this student.')

    fees = _fees_payload_for_student(student_profile)
    name = student_profile.user.get_full_name() or student_profile.user.email
    message = f'Reminder: {name} has an outstanding fee balance of ₦{fees["outstanding"]}. Please make payment at your earliest convenience. -{school.name}'
    threading.Thread(
        target=_send_attendance_sms_batch,
        args=([(phone, message)], settings.SCHOOLGATE_SMS_PROVIDER),
        daemon=True,
    ).start()
    return Response({'success': True, 'message': 'Fee reminder sent.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def classes_lookup(request):
    """Feeds the desktop app's class picker for Section 4c (Bulk Assign Cards) -
    students only, since "class" isn't a concept for staff."""
    if request.user.role not in ADMIN_ROLES:
        return _forbidden('Only school administrators can assign RFID cards.')

    school, error = _require_school(request.user, _school_code_from_request(request))
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

    school, error = _require_school(request.user, _school_code_from_request(request))
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

    school, error = _require_school(request.user, _school_code_from_request(request))
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
