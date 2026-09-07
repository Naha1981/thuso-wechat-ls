from app.services.whatsapp_reliability import MAX_ATTEMPTS, recover_stale_inbox_events


def test_inbox_retry_budget_is_explicit():
    assert MAX_ATTEMPTS == 8


def test_stale_recovery_is_exposed():
    assert callable(recover_stale_inbox_events)


def test_durable_worker_module_exists():
    from pathlib import Path
    assert Path('app/services/whatsapp_inbox_worker.py').exists()
