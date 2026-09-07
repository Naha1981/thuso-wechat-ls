from __future__ import annotations

from dataclasses import asdict, dataclass
import os


@dataclass(frozen=True)
class LesothoPaymentMethod:
    code: str
    name: str
    type: str
    provider: str
    currency: str = "LSL"
    live: bool = False
    internet_required: bool = True
    notes: str = ""


def _configured(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def list_lesotho_payment_methods() -> list[dict]:
    """Return a conservative customer-facing catalog.

    Only integrations with credentials are marked live. We never imply a direct
    issuer API exists when THUSO has not received production credentials/contracts.
    """
    methods = [
        LesothoPaymentMethod(
            code="mpesa",
            name="M-Pesa",
            type="mobile_money",
            provider="mopay_ls",
            live=_configured("MOPAY_API_KEY"),
            notes="Available through the MoPay Lesotho gateway when configured.",
        ),
        LesothoPaymentMethod(
            code="ecocash",
            name="EcoCash",
            type="mobile_money",
            provider="mopay_ls",
            live=_configured("MOPAY_API_KEY"),
            notes="Available through the MoPay Lesotho gateway when configured.",
        ),
        LesothoPaymentMethod(
            code="cpay",
            name="C-Pay",
            type="mobile_money",
            provider="chaperone_ls",
            live=_configured("CHAPERONE_API_KEY", "CHAPERONE_BASE_URL"),
            internet_required=False,
            notes="Chaperone supports C-Pay via mobile channels and a payment gateway; direct API activation requires an approved merchant integration.",
        ),
        LesothoPaymentMethod(
            code="khetsi",
            name="Khetsi",
            type="mobile_money",
            provider="khetsi_ls",
            live=_configured("KHETSI_API_KEY", "KHETSI_BASE_URL"),
            internet_required=False,
            notes="Khetsi is represented as a local payment rail; direct API activation requires an approved integration.",
        ),
        LesothoPaymentMethod(
            code="mywallet",
            name="My Wallet",
            type="mobile_money",
            provider="smartel_money_ls",
            live=_configured("SMARTEL_API_KEY", "SMARTEL_BASE_URL"),
            internet_required=False,
            notes="Smartel Money's My Wallet is represented as a local payment rail; direct API activation requires an approved integration.",
        ),
        LesothoPaymentMethod(
            code="card",
            name="Visa / Mastercard",
            type="card",
            provider="mopay_ls",
            live=_configured("MOPAY_API_KEY"),
            notes="Card acceptance is provided through the MoPay Lesotho gateway when configured.",
        ),
    ]
    return [asdict(method) for method in methods]
