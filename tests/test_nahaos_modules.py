from app.nahaos.modules import get_module, list_modules

def test_nahaos_module_catalog_contains_mega_app_domains():
    keys = {item["key"] for item in list_modules()}
    assert {"food", "transport", "ramalaisha", "business", "payments", "credit", "tax_trade", "agriculture", "telecom", "financial_literacy", "aegisgrid", "ai"} <= keys

def test_food_and_transport_are_live_foundation_modules():
    assert get_module("food").status == "live_foundation"
    assert get_module("transport").status == "live_foundation"

def test_provider_dependent_modules_are_explicitly_wired_not_falsely_live():
    assert get_module("ramalaisha").status == "wired"
    assert get_module("credit").status == "wired"
    assert get_module("telecom").status == "wired"
