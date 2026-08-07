"""Builds a student's complete history and freezes it into the archive.

`build_student_archive_payload()` is the single aggregator every read path in
this module goes through - the live view, the snapshot writer, and the printable
export all render the same shape, so an archived student and an active one look
identical on the page.

Nothing here writes to the records it reads. The archive is strictly read-only
by construction: the only row this module ever creates is its own snapshot.
"""
import datetime
import uuid
from decimal import Decimal

from django.utils import timezone

from .models import ArchivedStudentRecord

SNAPSHOT_VERSION = 1


def _jsonable(value):
    """Coerce a payload into something JSONField can store verbatim.

    The snapshot has to survive without the model layer that produced it, so
    Decimals become floats and dates become ISO strings here rather than
    relying on a serializer at read time.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _float(value):
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------
# Section builders. Each returns a plain dict/list and swallows nothing - a
# section that genuinely has no data returns an empty list, which the frontend
# renders as "No records".
# --------------------------------------------------------------------------


def _profile_section(student_profile, request=None):
    from users.app_views import _class_label, _profile_picture_url

    student_user = student_profile.user
    activity = getattr(student_profile, "extra_curricular_activity_title", None)
    return {
        "id": str(student_profile.id),
        "user_id": str(student_user.id),
        "student_id": student_profile.student_id,
        "admission_number": student_profile.admission_number,
        "name": student_user.get_full_name(),
        "first_name": student_user.first_name,
        "last_name": student_user.last_name,
        "email": student_user.email,
        "phone": student_user.phone,
        "gender": student_user.gender or "",
        "date_of_birth": student_user.date_of_birth,
        "profile_picture": _profile_picture_url(request, student_user),
        "state_of_origin": student_profile.state_of_origin,
        "local_government": student_profile.local_government,
        "home_address": student_profile.home_address,
        "student_type": student_profile.student_type,
        "current_class": _class_label(student_profile.current_class) if student_profile.current_class_id else "",
        "current_class_id": student_profile.current_class_id,
        "current_term": student_profile.current_term.name if student_profile.current_term_id else "",
        "is_active": student_user.is_active,
        "activity_title": activity.name if activity else "",
        "activity_stars": _float(getattr(activity, "star_rating", 0)) if activity else None,
        "created_at": student_profile.created_at,
    }


def _admission_section(student_profile):
    from users.app_views import _class_label

    enrollments = []
    for enrollment in student_profile.enrollments.select_related("assigned_class", "created_by").all():
        enrollments.append(
            {
                "id": str(enrollment.id),
                "assigned_class": _class_label(enrollment.assigned_class) if enrollment.assigned_class_id else "",
                "welcome_subject": enrollment.welcome_subject,
                "created_by": enrollment.created_by.get_full_name() if enrollment.created_by_id else "",
                "created_at": enrollment.created_at,
            }
        )

    payment_reference = getattr(student_profile, "payment_reference", None)
    return {
        "admission_number": student_profile.admission_number,
        "admission_date": student_profile.admission_date,
        "student_id": student_profile.student_id,
        "payment_reference": payment_reference.code if payment_reference else "",
        "id_card_generated_at": student_profile.id_card_generated_at,
        "id_card_viewed_at": student_profile.id_card_viewed_at,
        "enrollments": enrollments,
    }


def _guardian_section(student_profile):
    from users.models import ParentProfile

    guardians = []
    if student_profile.guardian_name:
        guardians.append(
            {
                "role": "Primary guardian",
                "name": student_profile.guardian_name,
                "phone": student_profile.guardian_phone,
                "email": student_profile.guardian_email,
                "relation": student_profile.guardian_relation,
            }
        )
    if student_profile.second_guardian_name:
        guardians.append(
            {
                "role": "Secondary guardian",
                "name": student_profile.second_guardian_name,
                "phone": student_profile.second_guardian_phone,
                "email": student_profile.second_guardian_email,
                "relation": student_profile.second_guardian_relation,
            }
        )

    linked_accounts = []
    for parent_profile in ParentProfile.objects.filter(children=student_profile).select_related("user"):
        linked_accounts.append(
            {
                "id": str(parent_profile.id),
                "name": parent_profile.user.get_full_name(),
                "email": parent_profile.user.email,
                "phone": parent_profile.user.phone,
                "occupation": parent_profile.occupation,
                "company": parent_profile.company,
                "preferred_contact": parent_profile.preferred_contact,
            }
        )

    return {"guardians": guardians, "linked_parent_accounts": linked_accounts}


def _medical_section(student_profile):
    return {
        "blood_group": student_profile.blood_group,
        "disability": student_profile.disability,
        "allergies": student_profile.allergies,
        "medical_conditions": student_profile.medical_conditions,
    }


def _attendance_section(student_profile):
    from academic.models import AttendanceRecord
    from users.app_views import _class_label

    records = (
        AttendanceRecord.objects.filter(student=student_profile.user)
        .select_related("class_group", "noted_by")
        .order_by("-date")
    )

    rows = []
    counts = {"present": 0, "absent": 0, "late": 0}
    for record in records:
        counts[record.status] = counts.get(record.status, 0) + 1
        rows.append(
            {
                "date": record.date,
                "status": record.status,
                "class_name": _class_label(record.class_group) if record.class_group_id else "",
                "noted_by": record.noted_by.get_full_name() if record.noted_by_id else "",
                "location": record.location_address or "",
                "clock_in_at": record.clock_in_at,
                "clock_out_at": record.clock_out_at,
                "hours_on_site": record.hours_on_site,
            }
        )

    total = len(rows)
    present_like = counts.get("present", 0) + counts.get("late", 0)
    return {
        "summary": {
            "total_days": total,
            "present": counts.get("present", 0),
            "absent": counts.get("absent", 0),
            "late": counts.get("late", 0),
            "attendance_rate": round((present_like / total) * 100, 2) if total else 0.0,
        },
        "records": rows,
    }


def _academic_section(student_profile, request=None):
    from academic.models import ResultBatch, StudentClassPromotion, StudentSubjectScore
    from users.app_views import _class_label, _student_result_report

    # Every score ever recorded, grouped into per-term report cards. Rejected
    # batches are excluded the same way _transcript_payload excludes them.
    scores = (
        StudentSubjectScore.objects.filter(student=student_profile)
        .exclude(approval_status=ResultBatch.REJECTED)
        .select_related("subject", "class_group", "term__academic_year", "teacher", "result_batch")
        .order_by("term__academic_year__start_date", "term__start_date", "subject__name")
    )

    report_cards = {}
    for item in scores:
        year_name = (
            item.term.academic_year.name
            if item.term_id and item.term.academic_year_id
            else "Unassigned Session"
        )
        term_name = item.term.name if item.term_id else "Unassigned Term"
        class_name = _class_label(item.class_group) if item.class_group_id else ""
        key = f"{year_name}||{term_name}||{class_name}"
        card = report_cards.setdefault(
            key,
            {
                "session": year_name,
                "term": term_name,
                "class_name": class_name,
                "subjects": [],
                "total_score": 0.0,
                "total_max": 0.0,
                "teacher_remarks": [],
                "principal_remark": "",
                "batch_note": "",
            },
        )
        card["subjects"].append(
            {
                "subject": item.subject.name if item.subject_id else "",
                "score": _float(item.score),
                "max_score": _float(item.max_score),
                "percentage": item.percentage,
                "grade": item.grade,
                "remark": item.performance_remark or item.remarks,
                "status": item.approval_status,
                "teacher": item.teacher.get_full_name() if item.teacher_id else "",
                "components": {
                    "theory": _float(item.theory_score),
                    "cbt": _float(item.cbt_score),
                    "assessment": _float(item.assessment_score),
                    "assignment": _float(item.assignment_score),
                    "attendance": _float(item.attendance_score),
                    "other": _float(item.other_score),
                },
                "published_at": item.published_at,
            }
        )
        card["total_score"] += _float(item.score)
        card["total_max"] += _float(item.max_score)
        if item.remarks and item.remarks not in card["teacher_remarks"]:
            card["teacher_remarks"].append(item.remarks)
        # The admin note on the result batch is where a principal's review
        # comment lands when a batch is approved or rejected.
        if item.result_batch_id and item.result_batch.admin_note and not card["batch_note"]:
            card["batch_note"] = item.result_batch.admin_note
            card["principal_remark"] = item.result_batch.admin_note

    cards = []
    for card in report_cards.values():
        card["average"] = (
            round((card["total_score"] / card["total_max"]) * 100, 2) if card["total_max"] else 0.0
        )
        card["subject_count"] = len(card["subjects"])
        card["total_score"] = round(card["total_score"], 2)
        card["total_max"] = round(card["total_max"], 2)
        cards.append(card)

    # Current-standing broadsheet position, computed by the same helper the
    # live Results screen uses so the numbers agree.
    try:
        broadsheet = _student_result_report(student_profile, request=request)
    except Exception:
        broadsheet = {}

    promotions = []
    for promotion in (
        StudentClassPromotion.objects.filter(student=student_profile)
        .select_related("from_class", "to_class", "from_term", "to_term", "from_academic_year", "to_academic_year", "promoted_by")
        .order_by("created_at")
    ):
        promotions.append(
            {
                "from_class": _class_label(promotion.from_class) if promotion.from_class_id else "",
                "to_class": _class_label(promotion.to_class) if promotion.to_class_id else "",
                "from_term": promotion.from_term.name if promotion.from_term_id else "",
                "to_term": promotion.to_term.name if promotion.to_term_id else "",
                "from_session": promotion.from_academic_year.name if promotion.from_academic_year_id else "",
                "to_session": promotion.to_academic_year.name if promotion.to_academic_year_id else "",
                "scope": promotion.scope,
                "note": promotion.note,
                "promoted_by": promotion.promoted_by.get_full_name() if promotion.promoted_by_id else "",
                "promoted_at": promotion.created_at,
            }
        )

    return {
        "report_cards": cards,
        "promotions": promotions,
        "broadsheet": {
            "class_position": broadsheet.get("class_position"),
            "class_size": broadsheet.get("class_size", 0),
            "total_score": broadsheet.get("total_score", 0),
            "average_score": broadsheet.get("average_score", 0),
        },
    }


def _exam_section(student_profile):
    from exams.models import ExamAttempt

    attempts = (
        ExamAttempt.objects.filter(student=student_profile.user)
        .select_related("exam")
        .order_by("-start_time")
    )

    rows = []
    for attempt in attempts:
        exam = attempt.exam
        rows.append(
            {
                "exam": getattr(exam, "title", "") or getattr(exam, "name", ""),
                "subject": getattr(getattr(exam, "subject", None), "name", ""),
                "score": _float(attempt.score),
                "total_points": _float(attempt.total_points),
                "percentage": _float(attempt.percentage),
                "is_completed": attempt.is_completed,
                "is_submitted": attempt.is_submitted,
                "auto_submitted": attempt.auto_submitted,
                "auto_submit_reason": attempt.auto_submit_reason_display or attempt.auto_submit_reason,
                "started_at": attempt.start_time,
                "ended_at": attempt.end_time,
                "graded_at": attempt.graded_at,
            }
        )
    return rows


def _finance_section(student_profile):
    from finance.models import BankPayment, FeeAllocation, SchoolFee
    from finance.services import bulk_fee_paid_amounts

    fees = list(
        SchoolFee.objects.filter(student=student_profile)
        .select_related("class_fee", "bill", "created_by")
        .order_by("-due_date")
    )

    invoices = []
    total_billed = Decimal("0.00")
    total_paid = Decimal("0.00")
    # Payments taken as cash or matched from a bank transfer are booked as
    # ledger rows, not onto SchoolFee.amount_paid - so an archive built from
    # that column would preserve, permanently, a debt the student had settled.
    paid_amounts = bulk_fee_paid_amounts(fees)
    for fee in fees:
        amount = Decimal(str(fee.amount or 0))
        paid = paid_amounts.get(fee.id, Decimal("0.00"))
        total_billed += amount
        total_paid += paid
        invoices.append(
            {
                "id": str(fee.id),
                "title": fee.title,
                "invoice_number": fee.invoice_number or "",
                "amount": _float(amount),
                "amount_paid": _float(paid),
                "outstanding": _float(max(amount - paid, Decimal("0.00"))),
                "currency": fee.currency,
                "status": fee.status,
                "due_date": fee.due_date,
                "payment_date": fee.payment_date,
                "last_payment_date": fee.last_payment_date,
                "source": "bill" if fee.bill_id else ("class_fee" if fee.class_fee_id else "manual"),
                "bill_title": fee.bill.title if fee.bill_id else "",
                "is_customized": fee.is_customized,
                "sent_at": fee.sent_at,
                "viewed_at": fee.viewed_at,
                "created_at": fee.created_at,
            }
        )

    # Payments/receipts: every allocation that actually moved money against one
    # of this student's fees, plus any bank payments recorded against them.
    payments = []
    allocations = (
        FeeAllocation.objects.filter(fee__student=student_profile)
        .select_related("fee", "transaction")
        .order_by("-created_at")
    )
    for allocation in allocations:
        transaction = allocation.transaction
        payments.append(
            {
                "id": str(allocation.id),
                "fee_title": allocation.fee.title if allocation.fee_id else "",
                "invoice_number": allocation.fee.invoice_number or "" if allocation.fee_id else "",
                "amount": _float(allocation.amount_allocated),
                "status": allocation.status,
                "reference": transaction.reference if allocation.transaction_id else "",
                "channel": transaction.provider if allocation.transaction_id else "",
                "narration": transaction.narration if allocation.transaction_id else "",
                "paid_at": allocation.created_at,
                "kind": "allocation",
            }
        )

    for bank_payment in BankPayment.objects.filter(student=student_profile).order_by("-created_at"):
        payments.append(
            {
                "id": str(bank_payment.id),
                "fee_title": bank_payment.narration or "Bank transfer",
                "invoice_number": bank_payment.receipt_number or "",
                "amount": _float(bank_payment.amount),
                "status": bank_payment.status,
                "reference": bank_payment.bank_reference,
                "channel": "bank_transfer",
                "paid_at": bank_payment.created_at,
                "kind": "bank_payment",
            }
        )

    # Discounts recorded on the bills this student was invoiced from. There is
    # no separate scholarship model in the platform today, so a scholarship is
    # represented the way the finance module already represents one: a discount
    # on the bill that produced the invoice.
    discounts = []
    seen_bills = set()
    for fee in fees:
        if not fee.bill_id or fee.bill_id in seen_bills:
            continue
        seen_bills.add(fee.bill_id)
        bill = fee.bill
        if bill and Decimal(str(bill.discount_amount or 0)) > 0:
            discounts.append(
                {
                    "source": bill.title,
                    "amount": _float(bill.discount_amount),
                    "type": "Bill discount",
                    "applied_at": bill.published_at or bill.created_at,
                }
            )

    return {
        "summary": {
            "total_billed": _float(total_billed),
            "total_paid": _float(total_paid),
            "outstanding": _float(max(total_billed - total_paid, Decimal("0.00"))),
            "invoice_count": len(invoices),
            "payment_count": len(payments),
        },
        "invoices": invoices,
        "payments": sorted(payments, key=lambda row: str(row.get("paid_at") or ""), reverse=True),
        "discounts": discounts,
        "scholarships": [],
    }


def _documents_section(student_profile, request=None):
    from users.app_views import _media_url

    documents = []
    for label, field in (
        ("Birth certificate", student_profile.birth_certificate),
        ("Previous school report", student_profile.previous_school_report),
    ):
        url = _media_url(request, field)
        if url:
            documents.append({"label": label, "url": url, "name": getattr(field, "name", "")})
    return documents


def _awards_section(student_profile):
    """Awards, honours, and offices held.

    The platform records these on the student's testimonial (prizes_and_honors /
    office_held) and as the profile's activity title - there is no standalone
    award model - so the archive surfaces exactly what is on file rather than
    inventing a new one.
    """
    awards = []
    testimonial = getattr(student_profile, "testimonial", None)
    if testimonial:
        if testimonial.prizes_and_honors and testimonial.prizes_and_honors.strip().upper() != "NIL":
            awards.append({"title": testimonial.prizes_and_honors, "type": "Prize / Honour", "source": "Testimonial"})
        if testimonial.office_held and testimonial.office_held.strip().upper() != "NIL":
            awards.append({"title": testimonial.office_held, "type": "Office held", "source": "Testimonial"})

    activity = getattr(student_profile, "extra_curricular_activity_title", None)
    if activity:
        awards.append(
            {
                "title": activity.name,
                "type": "Leadership / activity title",
                "source": "Student profile",
                "stars": _float(activity.star_rating),
            }
        )
    return awards


def _activities_section(student_profile):
    activities = []
    activity = getattr(student_profile, "extra_curricular_activity_title", None)
    if activity:
        activities.append({"name": activity.name, "stars": _float(activity.star_rating), "source": "Student profile"})

    testimonial = getattr(student_profile, "testimonial", None)
    if testimonial and testimonial.co_curricular_activities:
        text = testimonial.co_curricular_activities.strip()
        if text and text.upper() != "NIL":
            activities.append({"name": text, "stars": None, "source": "Testimonial"})
    return activities


def _discipline_section(student_profile):
    """Disciplinary records.

    No disciplinary model exists in the platform yet, so this returns an empty
    list and the page renders a "No records" state. The section is present so
    the archive shape does not change when one is added later.
    """
    return []


def _messages_section(student_profile):
    """Official correspondence sent to the student, newest first."""
    try:
        from notifications.models import InAppMessage
    except Exception:
        return []

    rows = []
    messages = (
        InAppMessage.objects.filter(recipient=student_profile.user)
        .select_related("sender")
        .order_by("-created_at")[:100]
    )
    for message in messages:
        rows.append(
            {
                "subject": message.subject,
                "body": message.body,
                "sender": message.sender.get_full_name() if message.sender_id else "",
                "sent_at": message.created_at,
                "is_read": message.is_read,
            }
        )
    return rows


# --------------------------------------------------------------------------
# Aggregator
# --------------------------------------------------------------------------


def build_student_archive_payload(student_profile, request=None):
    """Assemble every record ever associated with one student.

    Read-only: this touches nothing it reads. Each section is built
    independently so one unavailable subsystem cannot blank out the rest of a
    student's history.
    """
    from users.app_views import _school_payload

    sections = {}
    builders = {
        "profile": lambda: _profile_section(student_profile, request=request),
        "admission": lambda: _admission_section(student_profile),
        "guardians": lambda: _guardian_section(student_profile),
        "medical": lambda: _medical_section(student_profile),
        "attendance": lambda: _attendance_section(student_profile),
        "academics": lambda: _academic_section(student_profile, request=request),
        "exams": lambda: _exam_section(student_profile),
        "finance": lambda: _finance_section(student_profile),
        "documents": lambda: _documents_section(student_profile, request=request),
        "awards": lambda: _awards_section(student_profile),
        "activities": lambda: _activities_section(student_profile),
        "discipline": lambda: _discipline_section(student_profile),
        "correspondence": lambda: _messages_section(student_profile),
    }
    for key, builder in builders.items():
        try:
            sections[key] = builder()
        except Exception as exc:  # pragma: no cover - defensive
            sections[key] = {"error": f"Could not load this section: {exc}"}

    # Transcript and testimonial reuse the existing document builders so the
    # archive shows byte-identical content to the Transcripts & Testimonials
    # screen.
    try:
        from users.app_views import _transcript_payload

        sections["transcript"] = _transcript_payload(student_profile, request=request)
    except Exception as exc:  # pragma: no cover - defensive
        sections["transcript"] = {"error": f"Could not load transcript: {exc}"}

    try:
        from users.app_views import _testimonial_payload

        sections["testimonial"] = _testimonial_payload(
            getattr(student_profile, "testimonial", None), student_profile, request=request
        )
    except Exception as exc:  # pragma: no cover - defensive
        sections["testimonial"] = {"error": f"Could not load testimonial: {exc}"}

    try:
        sections["school"] = _school_payload(student_profile.user.tenant, request)
    except Exception:
        sections["school"] = {}

    sections["generated_at"] = timezone.now()
    sections["snapshot_version"] = SNAPSHOT_VERSION
    return _jsonable(sections)


# --------------------------------------------------------------------------
# Snapshot writer
# --------------------------------------------------------------------------


def _last_academic_year_for(student_profile):
    from academic.models import ResultBatch, StudentSubjectScore

    latest = (
        StudentSubjectScore.objects.filter(student=student_profile)
        .exclude(approval_status=ResultBatch.REJECTED)
        .select_related("term__academic_year")
        .order_by("-term__academic_year__start_date", "-term__start_date")
        .first()
    )
    if latest and latest.term_id and latest.term.academic_year_id:
        return latest.term.academic_year.name
    if student_profile.current_term_id and student_profile.current_term.academic_year_id:
        return student_profile.current_term.academic_year.name
    return ""


def snapshot_student(student_profile, reason=ArchivedStudentRecord.REASON_MANUAL, actor=None, note="", seal=False, request=None):
    """Freeze a student's full history into the permanent archive.

    Called on demand by an admin and automatically from the pre_delete signal.
    Re-running it for an unsealed record refreshes the snapshot in place; a
    sealed record is never touched.
    """
    from users.app_views import _class_label, _profile_picture_url

    student_user = student_profile.user
    existing = ArchivedStudentRecord.objects.filter(source_student=student_profile).first()
    if existing is None:
        existing = ArchivedStudentRecord.objects.filter(
            tenant=student_user.tenant, student_id=student_profile.student_id
        ).first()

    if existing is not None and existing.is_sealed:
        return existing

    payload = build_student_archive_payload(student_profile, request=request)
    last_class = _class_label(student_profile.current_class) if student_profile.current_class_id else ""
    academic_year = _last_academic_year_for(student_profile)

    values = {
        "tenant": student_user.tenant,
        "source_student": student_profile,
        "student_id": student_profile.student_id,
        "admission_number": student_profile.admission_number or "",
        "full_name": student_user.get_full_name(),
        "email": student_user.email or "",
        "gender": student_user.gender or "",
        "profile_picture_url": _profile_picture_url(request, student_user) or "",
        "last_class_name": last_class,
        "last_class_id": student_profile.current_class_id,
        "last_academic_year": academic_year,
        "admission_date": student_profile.admission_date,
        "graduation_year": (academic_year or "").split("/")[-1].strip() if academic_year else "",
        "archive_reason": reason,
        "snapshot": payload,
        "snapshot_version": SNAPSHOT_VERSION,
    }
    if note:
        values["archive_note"] = note
    if actor is not None:
        values["archived_by"] = actor

    if existing is None:
        record = ArchivedStudentRecord(**values)
    else:
        record = existing
        for field, value in values.items():
            setattr(record, field, value)

    if seal:
        record.is_sealed = True
        record.sealed_at = timezone.now()
        record.source_student = None

    record.save()
    return record


def seal_archive_for_student(student_profile, reason=ArchivedStudentRecord.REASON_DELETED, actor=None, note=""):
    """Snapshot then permanently seal - the path taken when a student is deleted."""
    return snapshot_student(student_profile, reason=reason, actor=actor, note=note, seal=True)


def graduate_student_to_alumni(student_profile, actor=None, note="", reason=ArchivedStudentRecord.REASON_GRADUATED):
    """Move a student out of the active roll and into the alumni archive.

    Deliberately does *not* seal: the student's rows are still in the database,
    so the archive can keep reading them live and stay accurate. Sealing happens
    only if they are later deleted, at which point the pre_delete signal takes a
    final snapshot.

    The student account is deactivated and unassigned from its class, which is
    what keeps a graduate out of every active-student list on the platform.
    """
    record = snapshot_student(student_profile, reason=reason, actor=actor, note=note)

    student_user = student_profile.user
    if student_user.is_active:
        student_user.is_active = False
        student_user.save(update_fields=["is_active"])

    if student_profile.current_class_id is not None:
        student_profile.current_class = None
        student_profile.save(update_fields=["current_class"])

    return record


def archived_record_payload(record):
    """List-row shape for an archived student."""
    return {
        "key": f"archived:{record.id}",
        "record_id": str(record.id),
        "student_id": record.student_id,
        "admission_number": record.admission_number,
        "name": record.full_name,
        "email": record.email,
        "gender": record.gender,
        "profile_picture": record.profile_picture_url,
        "class_name": record.last_class_name,
        "academic_year": record.last_academic_year,
        "admission_date": record.admission_date.isoformat() if record.admission_date else None,
        "graduation_year": record.graduation_year,
        "archive_reason": record.archive_reason,
        "archive_reason_display": record.get_archive_reason_display(),
        "archived_at": record.archived_at.isoformat() if record.archived_at else None,
        "is_sealed": record.is_sealed,
        "status": record.get_archive_reason_display(),
    }
