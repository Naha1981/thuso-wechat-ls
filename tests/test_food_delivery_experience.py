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


def test_food_checkout_requires_location_and_starts_routed_payment():
    source = Path("app/api/food.py").read_text()
    assert "@router.post('/checkout')" in source
    assert "get_default_location" in source
    assert "initiate_routed_payment" in source
    assert "verified phone number required for payment" in source


def test_low_bandwidth_customer_web_exists():
    page = Path("web/app/page.js").read_text()
    css = Path("web/app/globals.css").read_text()
    assert "THUSO" in page
    assert "NEXT_PUBLIC_API_BASE" in Path("web/lib/api.js").read_text()
    assert "@media(max-width:520px)" in css
    assert "<img" not in page
