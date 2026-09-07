from app.services.lesotho_payment_methods import list_lesotho_payment_methods


def test_lesotho_catalog_is_mobile_money_first(monkeypatch):
    monkeypatch.setenv("MOPAY_API_KEY", "test-key")
    methods = list_lesotho_payment_methods()
    codes = {m["code"] for m in methods}
    assert {"mpesa", "ecocash", "cpay", "khetsi", "mywallet", "card"} <= codes
    assert methods[0]["code"] == "mpesa"
    assert methods[1]["code"] == "ecocash"
    assert methods[0]["live"] is True
    assert methods[1]["live"] is True


def test_direct_rails_are_not_claimed_live_without_credentials(monkeypatch):
    for key in (
        "MOPAY_API_KEY",
        "CHAPERONE_API_KEY",
        "CHAPERONE_BASE_URL",
        "KHETSI_API_KEY",
        "KHETSI_BASE_URL",
        "SMARTEL_API_KEY",
        "SMARTEL_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    methods = list_lesotho_payment_methods()
    live = {m["code"] for m in methods if m["live"]}
    assert live == set()
