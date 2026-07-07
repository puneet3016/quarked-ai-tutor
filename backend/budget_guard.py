from __future__ import annotations
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from fastapi import HTTPException
from supabase import create_client, Client
from cryptography.fernet import Fernet

# ----------------------------------------------------------------------
# Fail-fast config
# ----------------------------------------------------------------------
def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"{name} is required but missing from environment variables.")
    return v

# All required variables fail-fast on startup
SUPABASE_URL         = _require("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _require("SUPABASE_SERVICE_KEY")
QUESTION_ENC_KEY     = _require("QUESTION_ENC_KEY")

# Model Constraint: strictly use gemini-2.5-flash
MODEL = "gemini-2.5-flash"

# Live per-1M-token prices (USD) as of June 2026.
# gemini-1.5-flash and gemini-2.0-flash are retired.
# gemini-3.5-flash is too expensive for routine use.
PRICES = {
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40},
    "gemini-2.5-flash":      {"in": 0.30, "out": 2.50},
    "gemini-3.5-flash":      {"in": 1.50, "out": 9.00},
}

# The hard cap. INR to pay per month.
MONTHLY_BUDGET_INR = float(os.getenv("MONTHLY_BUDGET_INR", "5000"))
USD_INR_RATE       = float(os.getenv("USD_INR_RATE", "86"))       # Google billing rate
GST_MULTIPLIER     = float(os.getenv("GST_MULTIPLIER", "1.18"))   # 18% India GST

# Convert all-in INR cap to raw USD API spend budget
MONTHLY_BUDGET_USD = MONTHLY_BUDGET_INR / (USD_INR_RATE * GST_MULTIPLIER)

# Daily cap per student to prevent spamming
PER_STUDENT_DAILY_REQUEST_CAP = int(os.getenv("PER_STUDENT_DAILY_REQUEST_CAP", "50"))

# Maximum output limit per call. Must match the cap actually used by the tutor stream
# (gemini_client.get_tutor_response_stream) so check_budget's worst-case estimate is honest.
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))

# Fernet encryption key setup
_fernet = Fernet(QUESTION_ENC_KEY.encode())

def encrypt_text(plaintext: str | None) -> str | None:
    """Encrypt raw question text before database insertion. Returns base64 cipher."""
    if not plaintext:
        return None
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt_text(ciphertext: str | None) -> str | None:
    """Decrypt ciphertext on retrieval. Returns None if already purged."""
    if not ciphertext:
        return None
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        print(f"Error decrypting question: {e}")
        return "[Decryption Failed]"

# Supabase Client setup using service role key
_sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def sb() -> Client:
    return _sb

# ----------------------------------------------------------------------
# Cost Helpers
# ----------------------------------------------------------------------
def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICES.get(model)
    if not p:
        raise ValueError(f"Unknown / unpriced model: {model}")
    return (input_tokens / 1e6 * p["in"]) + (output_tokens / 1e6 * p["out"])

def month_spent_usd() -> float:
    """Gets total spent USD for current month from the pre-aggregated view (avoids 1000-row limit)."""
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    try:
        res = (
            sb().table("monthly_spend_usd")
            .select("spent_usd")
            .gte("month", month_start)
            .execute()
        )
        if res.data:
            return sum(float(r["spent_usd"]) for r in res.data)
        return 0.0
    except Exception as e:
        print(f"Error checking monthly spend: {e}")
        return 0.0

# ----------------------------------------------------------------------
# Safety Layer 1: Consent Gating
# ----------------------------------------------------------------------
def require_consent(student_id: str, purpose: str = "tutoring") -> None:
    """Raise 403 unless the student has granted consent for target purpose."""
    try:
        res = (
            sb().table("consents")
            .select("status")
            .eq("student_id", student_id)
            .eq("purpose", purpose)
            .eq("status", "granted")
            .limit(1)
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=403,
                detail=f"Consent for '{purpose}' has not been granted by a parent. Access denied.",
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking consent gate: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify student consent status.")

def is_analytics_consented(student_id: str) -> bool:
    """Check if the student has granted consent for weak_topic_analytics."""
    try:
        res = (
            sb().table("consents")
            .select("status")
            .eq("student_id", student_id)
            .eq("purpose", "weak_topic_analytics")
            .eq("status", "granted")
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        print(f"Error checking weak_topic_analytics consent: {e}")
        return False

# ----------------------------------------------------------------------
# Safety Layer 2: Budget Gating
# ----------------------------------------------------------------------
@dataclass
class BudgetStatus:
    spent_usd: float
    budget_usd: float
    spent_inr_allin: float
    budget_inr_allin: float
    remaining_pct: float

def check_budget(estimated_input_tokens: int) -> BudgetStatus:
    """Block calls if the upcoming interaction's worst-case cost exceeds the monthly limit."""
    spent = month_spent_usd()
    upcoming = cost_usd(MODEL, estimated_input_tokens, MAX_OUTPUT_TOKENS)

    if spent + upcoming > MONTHLY_BUDGET_USD:
        spent_inr = spent * USD_INR_RATE * GST_MULTIPLIER
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly AI budget reached "
                f"(spent ~Rs{spent_inr:.0f} of Rs{MONTHLY_BUDGET_INR:.0f}). "
                f"Service paused until next month or until the cap is raised."
            ),
        )

    return BudgetStatus(
        spent_usd=spent,
        budget_usd=MONTHLY_BUDGET_USD,
        spent_inr_allin=spent * USD_INR_RATE * GST_MULTIPLIER,
        budget_inr_allin=MONTHLY_BUDGET_INR,
        remaining_pct=100 * (1 - (spent + upcoming) / MONTHLY_BUDGET_USD),
    )

def check_student_daily_cap(student_id: str) -> None:
    """Verifies student hasn't exceeded daily token/turn limit (prevents runaway chat spamming)."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    try:
        res = (
            sb().table("interactions")
            .select("id", count="exact")
            .eq("student_id", student_id)
            .gte("created_at", today)
            .limit(1)
            .execute()
        )
        if (res.count or 0) >= PER_STUDENT_DAILY_REQUEST_CAP:
            raise HTTPException(
                status_code=429,
                detail="Daily question limit reached for this student.",
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking student daily cap: {e}")

# ----------------------------------------------------------------------
# Budget Alert (email the owner as spend approaches the cap)
# ----------------------------------------------------------------------
# Where to send the "budget getting high" heads-up. Override in Railway if needed.
ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "puneet301508@gmail.com")
# Send once per month at each of these % thresholds (before the 100% hard pause).
ALERT_THRESHOLDS = [80, 95]

def _send_alert_email(subject: str, body: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("OTP_FROM_EMAIL")
    if not (api_key and sender and ADMIN_ALERT_EMAIL):
        return
    try:
        import requests
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": sender, "to": [ADMIN_ALERT_EMAIL], "subject": subject, "text": body},
            timeout=10,
        )
    except Exception as e:
        print(f"Budget alert email failed: {e}")

def maybe_send_budget_alert() -> None:
    """Email the owner once per month per threshold as spend climbs toward the cap.
    Dedup is via the budget_alerts table (PK month+threshold). Safe no-op if that table
    doesn't exist yet or email isn't configured. Meant to run in a background task."""
    try:
        if MONTHLY_BUDGET_USD <= 0:
            return
        spent = month_spent_usd()
        pct = 100 * spent / MONTHLY_BUDGET_USD
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        for thr in ALERT_THRESHOLDS:
            if pct < thr:
                continue
            existing = (
                sb().table("budget_alerts")
                .select("threshold")
                .eq("month", month_key)
                .eq("threshold", thr)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue
            # Insert BEFORE sending so a race can't double-send (PK month+threshold).
            sb().table("budget_alerts").insert({"month": month_key, "threshold": thr}).execute()
            spent_inr = spent * USD_INR_RATE * GST_MULTIPLIER
            _send_alert_email(
                subject=f"Quarked AI budget at {thr}% (~Rs{spent_inr:.0f} of Rs{MONTHLY_BUDGET_INR:.0f})",
                body=(
                    f"Heads up — your Quarked AI tutor spend for {month_key} has reached "
                    f"{pct:.0f}% of the monthly cap.\n\n"
                    f"Spent so far: ~Rs{spent_inr:.0f} (all-in, incl. 18% GST)\n"
                    f"Monthly cap:  Rs{MONTHLY_BUDGET_INR:.0f}\n\n"
                    f"At 100% the tutor automatically pauses (students see a 'budget reached' "
                    f"message) until next month, or until you raise MONTHLY_BUDGET_INR in Railway.\n"
                ),
            )
    except Exception as e:
        print(f"maybe_send_budget_alert error: {e}")

# ----------------------------------------------------------------------
# Log Writer Wrapper
# ----------------------------------------------------------------------
def log_interaction(*, session_id, student_id, model, input_tokens, output_tokens,
                    subject=None, topic=None, difficulty=None, resolved=None,
                    question_text=None) -> dict | None:
    """Encrypts question text ONLY if analytics consent is granted, then logs to DB."""
    try:
        db_question_text = None
        if question_text and is_analytics_consented(student_id):
            db_question_text = encrypt_text(question_text)
            
        row = sb().table("interactions").insert({
            "session_id": session_id,
            "student_id": student_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd(model, input_tokens, output_tokens), 6),
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "resolved": resolved,
            "question_text": db_question_text,
        }).execute()
        # Fire a budget heads-up email if this pushed spend past a threshold (deduped/month).
        maybe_send_budget_alert()
        return row.data[0] if row.data else None
    except Exception as e:
        print(f"Error logging interaction: {e}")
        return None
