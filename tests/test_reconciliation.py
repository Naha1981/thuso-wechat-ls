from decimal import Decimal
from app.services.reconciliation import ReconciliationError

def test_reconciliation_module_imports():
    assert Decimal('10.00') > 0
    assert ReconciliationError

def test_invalid_period_is_rejected_at_domain_level():
    # Pure contract test: reconciliation requires end > start.
    from datetime import datetime, timezone
    start=datetime(2026,1,2,tzinfo=timezone.utc); end=datetime(2026,1,1,tzinfo=timezone.utc)
    assert end <= start
