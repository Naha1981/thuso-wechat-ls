from pathlib import Path


def test_food_vertical_routes_are_registered():
    source = Path("app/main.py").read_text()
    assert "from app.api.food import router as food_router" in source
    assert "app.include_router(food_router" in source


def test_food_delivery_migration_exists():
    migration = Path("supabase/migrations/034_food_delivery_experience.sql")
    assert migration.exists()
    sql = migration.read_text()
    assert "customer_addresses" in sql
    assert "commerce_events_order_created_idx" in sql


def test_customer_food_service_exists():
    source = Path("app/services/food_delivery.py").read_text()
    for name in ("save_customer_location", "customer_orders", "order_timeline", "cancel_customer_order"):
        assert f"async def {name}" in source



def test_customer_cancel_is_payment_safe():
    source = Path("app/services/food_delivery.py").read_text()
    assert "and status='pending_payment' returning *" in source
    assert "and status in ('pending_payment','paid','preparing')" not in source
