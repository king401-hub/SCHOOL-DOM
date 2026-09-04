"""Nightly term/session auto-advancement. See academic/models.py's
TermTransitionState docstring and academic/models.py's
sync_implicit_term_for_non_k12_year for the two halves this depends on."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def advance_terms():
    """
    Daily check: for every tenant whose active Term has passed its end_date,
    advance to the next Term if one already exists (never auto-creates a
    Term/AcademicYear - that's an admin decision, same as everywhere else in
    this app), otherwise flag that the school needs to set one up. Either
    way, queues a school-wide TermTransitionState for the admin popup and
    fires an in-app Notification. Skips a tenant that already has an
    unresolved transition, so a slow admin can't have it silently overwritten
    by a later run.
    """
    from django.utils import timezone

    from core.tenant import SchoolTenant
    from notifications.models import Notification
    from users.models import User

    from .models import AcademicYear, Term, TermTransitionState, sync_implicit_term_for_non_k12_year, _is_non_k12_legacy_tenant

    today = timezone.localdate()
    advanced = 0
    skipped_unresolved = 0
    errors = 0

    ended_terms = list(
        Term.objects.filter(is_active=True, end_date__lt=today).select_related("academic_year", "tenant")
    )
    for term in ended_terms:
        legacy_tenant = term.tenant
        if not legacy_tenant:
            continue
        try:
            if TermTransitionState.objects.filter(tenant=legacy_tenant, is_resolved=False).exists():
                skipped_unresolved += 1
                continue

            is_non_k12 = _is_non_k12_legacy_tenant(legacy_tenant)

            next_term = (
                Term.objects.filter(tenant=legacy_tenant, academic_year=term.academic_year, start_date__gt=term.start_date)
                .order_by("start_date")
                .first()
            )
            session_also_ended = is_non_k12
            if not next_term and term.academic_year_id:
                next_year = (
                    AcademicYear.objects.filter(tenant=legacy_tenant, start_date__gt=term.academic_year.start_date)
                    .order_by("start_date")
                    .first()
                )
                if next_year:
                    # Self-heal: a non-K12 school's next year might already
                    # exist without its implicit term yet (e.g. created via
                    # Django admin before this feature shipped).
                    sync_implicit_term_for_non_k12_year(next_year)
                    next_term = Term.objects.filter(tenant=legacy_tenant, academic_year=next_year).order_by("start_date").first()
                session_also_ended = True

            term.is_active = False
            term.save(update_fields=["is_active", "updated_at"])

            next_term_missing = next_term is None
            if next_term:
                next_term.is_active = True
                next_term.save(update_fields=["is_active", "updated_at"])
                if next_term.academic_year_id and next_term.academic_year_id != term.academic_year_id:
                    AcademicYear.objects.filter(tenant=legacy_tenant, id=term.academic_year_id).update(is_active=False)
                    AcademicYear.objects.filter(tenant=legacy_tenant, id=next_term.academic_year_id).update(is_active=True)

            TermTransitionState.objects.update_or_create(
                tenant=legacy_tenant,
                defaults={
                    "ended_term": term,
                    "session_also_ended": session_also_ended,
                    "next_term_missing": next_term_missing,
                    "is_resolved": False,
                    "resolved_by": None,
                    "resolved_at": None,
                },
            )

            school = SchoolTenant.objects.filter(schema_name__iexact=legacy_tenant.slug).first()
            if school:
                if next_term_missing:
                    message = f"{term.name} has ended and no next term is set up yet. Please configure the next term/session."
                elif session_also_ended:
                    message = f"{term.name} has ended, moving into {next_term.name}. The academic session has also ended - student promotion is ready to review."
                else:
                    message = f"{term.name} has ended. You're now in {next_term.name}."
                admins = User.objects.filter(
                    tenant=school, role__in=["school_admin", "principal", "school_superadmin"], is_active=True
                )
                for admin in admins:
                    try:
                        Notification.objects.create(
                            tenant=school,
                            user=admin,
                            title="Term ended" if not session_also_ended else "Academic session ended",
                            message=message,
                            notification_type="reminder",
                            priority=2,
                            channel="in_app",
                            event_type="term_transition",
                            action_text="Review",
                            deep_link="/dashboard",
                            is_delivered=True,
                            delivered_at=timezone.now(),
                        )
                    except Exception:
                        logger.warning("Term transition notification failed for tenant %s", legacy_tenant.slug, exc_info=True)

            advanced += 1
        except Exception:
            errors += 1
            logger.exception("advance_terms failed for tenant %s", getattr(legacy_tenant, "slug", legacy_tenant.pk))

    return {"advanced": advanced, "skipped_unresolved": skipped_unresolved, "errors": errors}
