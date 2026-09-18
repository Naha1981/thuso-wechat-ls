from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ModuleStatus = Literal["live_foundation", "wired", "provider_required"]

@dataclass(frozen=True)
class NahaOSModule:
    key: str
    name: str
    description: str
    status: ModuleStatus
    capabilities: tuple[str, ...]

MODULES: tuple[NahaOSModule, ...] = (
    NahaOSModule("identity", "Identity", "One citizen, business or organisation identity across NahaOS.", "live_foundation", ("profiles", "sessions", "consent")),
    NahaOSModule("government", "Government Services", "Digital public services, applications, certificates, tax and service status.", "wired", ("applications", "documents", "case_status", "notifications")),
    NahaOSModule("health", "Health", "Appointments, referrals, records and health-related service journeys.", "wired", ("appointments", "referrals", "records")),
    NahaOSModule("education", "Education", "Schools, exams, qualifications, bursaries and learning services.", "wired", ("applications", "results", "qualifications", "bursaries")),
    NahaOSModule("justice", "Justice", "Cases, legal documents, court workflows and legal-aid journeys.", "wired", ("cases", "documents", "legal_aid")),
    NahaOSModule("employment", "Jobs & Skills", "CVs, jobs, applications and qualification verification.", "wired", ("cv", "job_search", "applications", "verification")),
    NahaOSModule("food", "Food Ordering", "Discover merchants, menus, checkout, delivery and order tracking.", "live_foundation", ("restaurants", "cart", "checkout", "delivery", "tracking")),
    NahaOSModule("transport", "Transport", "Request rides and other transport services through the service marketplace.", "live_foundation", ("ride_requests", "offers", "tracking")),
    NahaOSModule("shopping", "Shopping", "Product discovery, ordering, fulfilment and delivery.", "wired", ("catalogues", "orders", "delivery")),
    NahaOSModule("ramalaisha", "Ramalaisha", "Diaspora-to-family grocery and retail fulfilment with secure pickup/delivery.", "wired", ("family_orders", "retailer_fulfilment", "otp_pickup", "backorders")),
    NahaOSModule("business", "SME Business", "Business operations including sales, inventory, expenses and merchant workflows.", "live_foundation", ("merchant_accounts", "pos", "inventory", "sales")),
    NahaOSModule("payments", "Payments", "Route payments across supported banks, wallets and payment partners.", "live_foundation", ("payment_methods", "routing", "webhooks", "reconciliation")),
    NahaOSModule("credit", "Credit & Lending", "Transaction-informed eligibility, financing and repayment workflows.", "wired", ("eligibility", "applications", "repayments", "risk_signals")),
    NahaOSModule("tax_trade", "Tax & Cross-Border Trade", "Tax classification, reporting, trade records and customs-ready data.", "wired", ("vat", "tax_reporting", "trade", "manifests", "anomaly_detection")),
    NahaOSModule("agriculture", "Agriculture", "Farmer services, inputs, markets, yield intelligence and supply forecasting.", "wired", ("farmer_profiles", "input_orders", "market_info", "forecasting")),
    NahaOSModule("telecom", "Telecom", "Airtime, bundles and future authenticated telecom commerce.", "wired", ("airtime", "bundles", "subscriptions")),
    NahaOSModule("travel", "Travel", "Travel discovery, bookings and related service coordination.", "wired", ("transport", "accommodation", "itineraries")),
    NahaOSModule("logistics", "Logistics", "Courier, delivery and broader fulfilment workflows.", "wired", ("dispatch", "tracking", "proof_of_delivery")),
    NahaOSModule("financial_literacy", "Financial Literacy", "WhatsApp-first lessons and personalised money guidance.", "wired", ("micro_lessons", "budgeting", "profit_explanations", "coaching")),
    NahaOSModule("aegisgrid", "AegisGrid Intelligence", "Risk, fraud, anomaly and decision-support signals across the platform.", "wired", ("fraud_detection", "risk_scoring", "anomaly_detection", "credit_signals")),
    NahaOSModule("ai", "AI Gateway", "The orchestration layer that understands requests and selects safe tools/services.", "live_foundation", ("chat", "routing", "tool_selection", "traceability")),
    NahaOSModule("integration_hub", "Integration Hub", "Adapters for government, enterprise, telecom, commerce, payments and AI providers.", "live_foundation", ("provider_adapters", "configuration", "health_checks", "audit")),
)

def list_modules() -> list[dict]:
    return [asdict(module) for module in MODULES]

def get_module(key: str) -> NahaOSModule | None:
    return next((module for module in MODULES if module.key == key), None)
