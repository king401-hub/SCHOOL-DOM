try:
    from celery import shared_task
except Exception:  # pragma: no cover - Celery is optional in local dev until installed.
    def shared_task(func=None, **_kwargs):
        def decorator(inner):
            return inner
        return decorator(func) if func else decorator

from fee_collections.services import create_due_settlements, process_settlement


@shared_task
def create_due_fee_settlements():
    settlements = create_due_settlements()
    return [str(item.id) for item in settlements]


@shared_task
def process_fee_settlement(settlement_id):
    settlement = process_settlement(settlement_id)
    return {"id": str(settlement.id), "status": settlement.status}


@shared_task
def run_collection_settlement_cycle():
    settlements = create_due_settlements()
    processed = [process_settlement(item.id) for item in settlements]
    return [{"id": str(item.id), "status": item.status} for item in processed]
