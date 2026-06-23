from __future__ import annotations
import hmac, hashlib, os, secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import requests
from supabase import create_client, Client

# ----------------------------------------------------------------------
# Fail-fast config
# ----------------------------------------------------------------------
def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"{name} is required but missing from environment.")
    return v

# All required variables fail-fast on startup
OTP_PEPPER  = _require("OTP_PEPPER")
TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))
CODE_DIGITS = 6

_sb: Client | None = None

def sb() -> Client:
    global _sb
    if _sb is None:
        _sb = create_client(_require("SUPABASE_URL"), _require("SUPABASE_SERVICE_KEY"))
    return _sb


# ----------------------------------------------------------------------
# Hashing (never store the raw code)
# ----------------------------------------------------------------------
def _hash(code: str) -> str:
    return hmac.new(OTP_PEPPER.encode(), code.encode(), hashlib.sha256).hexdigest()


def _gen_code() -> str:
    # cryptographically random, zero-padded
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


# ----------------------------------------------------------------------
# Sender interface
# ----------------------------------------------------------------------
class OtpSender(ABC):
    channel: str
    @abstractmethod
    def send(self, destination: str, code: str) -> None: ...


class EmailSender(OtpSender):
    channel = "email"

    def __init__(self):
        self.api_key = _require("RESEND_API_KEY")
        self.sender  = _require("OTP_FROM_EMAIL")  # e.g. "Quarked <consent@yourdomain.com>"

    def send(self, destination: str, code: str) -> None:
        body = (
            f"Your Quarked consent verification code is: {code}\n\n"
            f"It expires in {TTL_SECONDS // 60} minutes. If you did not request this, ignore this email."
        )
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"from": self.sender, "to": [destination],
                  "subject": "Your Quarked verification code", "text": body},
            timeout=10,
        )
        r.raise_for_status()


_SENDERS: dict[str, type[OtpSender]] = {"email": EmailSender}


def get_sender(channel: str) -> OtpSender:
    if channel not in _SENDERS:
        raise ValueError(f"OTP channel '{channel}' not enabled yet. Available: {list(_SENDERS)}")
    return _SENDERS[channel]()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
def request_otp(destination: str, channel: str = "email") -> str:
    """Generate, store (hashed), and send a code. Returns the challenge_id."""
    code = _gen_code()
    expires = datetime.now(timezone.utc) + timedelta(seconds=TTL_SECONDS)
    row = sb().table("otp_challenges").insert({
        "destination": destination,
        "channel": channel,
        "code_hash": _hash(code),
        "expires_at": expires.isoformat(),
    }).execute()
    challenge_id = row.data[0]["id"]
    get_sender(channel).send(destination, code)   # send AFTER store; never log `code`
    return challenge_id


def verify_otp(challenge_id: str, code: str) -> tuple[bool, str | None]:
    """
    Verify a code. Returns (ok, destination). Single-use; attempt-limited; expiry-checked.
    On success, marks the challenge consumed so it can't be replayed.
    """
    res = sb().table("otp_challenges").select("*").eq("id", challenge_id).limit(1).execute()
    if not res.data:
        return False, None
    c = res.data[0]

    if c["consumed_at"] is not None:
        return False, None
    if datetime.fromisoformat(c["expires_at"]) < datetime.now(timezone.utc):
        return False, None
    if c["attempts"] >= c["max_attempts"]:
        return False, None

    # always record the attempt
    sb().table("otp_challenges").update({"attempts": c["attempts"] + 1}).eq("id", challenge_id).execute()

    if not hmac.compare_digest(c["code_hash"], _hash(code)):   # constant-time compare
        return False, None

    sb().table("otp_challenges").update(
        {"consumed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", challenge_id).execute()
    return True, c["destination"]
