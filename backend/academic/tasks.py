"""Nightly term/session auto-advancement. See academic/models.py's
TermTransitionState docstring and check_and_advance_term_transition for the
per-tenant logic this just sweeps across every school - also called
synchronously from the admin dashboard endpoint so the popup doesn't
depend on Celery actually running in production."""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def advance_terms():
    """
    Daily sweep: for every tenant whose active Term has passed its end_date,
    run check_and_advance_term_transition. Exists as a safety net for a
    school nobody has logged into in a while - the primary trigger is the
    synchronous check on admin dashboard load (see users/app_views.py's
    dashboard_snapshot), since this project has no confirmed Celery worker
    in production.
    """
    from django.utils import timezone

    from .models import Term, TermTransitionState, check_and_advance_term_transition

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
            state = check_and_advance_term_transition(legacy_tenant)
            if state:
                advanced += 1
        except Exception:
            errors += 1
            logger.exception("advance_terms failed for tenant %s", getattr(legacy_tenant, "slug", legacy_tenant.pk))

    return {"advanced": advanced, "skipped_unresolved": skipped_unresolved, "errors": errors}
