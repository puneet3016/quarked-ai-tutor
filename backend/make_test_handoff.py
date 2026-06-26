"""
make_test_handoff.py  —  TEST ONLY.

Creates a throwaway student, grants tutoring + analytics consent (so the triggers
flip `active` and the consent gate passes), mints a valid exchange code, and prints
a ready-to-open URL. Opening that URL makes the widget exchange the code for the
90-day cookie — letting you verify the authenticated tutor end-to-end before the
real parent-consent page exists.

Run (so it picks up your real Supabase + OTP_PEPPER from Railway):
    railway run python3 make_test_handoff.py "https://YOUR-SUBJECT-PAGE-URL/maths.html"

If you omit the URL it defaults to https://app.quarked.tech/maths.html — replace
with whatever page actually embeds the widget.
"""
import os
import sys
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

from supabase import create_client


def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        sys.exit(f"{name} is required but missing from environment (run via `railway run`).")
    return v


sb = create_client(_req("SUPABASE_URL"), _req("SUPABASE_SERVICE_KEY"))
PEPPER = _req("OTP_PEPPER")
BASE = sys.argv[1] if len(sys.argv) > 1 else "https://app.quarked.tech/maths.html"


def hash_code(code: str) -> str:
    return hmac.new(PEPPER.encode(), code.encode(), hashlib.sha256).hexdigest()


# 1. throwaway student
student = sb.table("students").insert({
    "name": "Handoff Test Student",
    "grade": "Year 11",
    "board": "IGCSE",
    "parent_name": "Test Parent",
    "parent_email": "test-parent@example.com",
    "is_minor": True,
    "active": False,
}).execute().data[0]
sid = student["id"]

# 2. grant consent (DB triggers flip active=True + log consent_events)
for purpose in ("tutoring", "weak_topic_analytics"):
    sb.table("consents").insert({
        "student_id": sid,
        "purpose": purpose,
        "status": "granted",
        "granted_by": "Test Parent",
        "verify_method": "manual",   # test handoff; real flow uses 'otp'
        "verify_ref": "test-handoff",
    }).execute()

# 3. mint an exchange code (valid 1 hour for convenience; real ones expire in 5 min)
code = str(uuid.uuid4())
sb.table("exchange_codes").insert({
    "student_id": sid,
    "code_hash": hash_code(code),
    "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
}).execute()

sep = "&" if "?" in BASE else "?"
print("\n=== TEST HANDOFF READY ===")
print(f"student_id : {sid}")
print(f"exchange   : {code}")
print(f"OPEN THIS  : {BASE}{sep}code={code}")
print("\nOpening that URL exchanges the code for a 90-day cookie, then the chat uses /ask")
print("(unlimited, logged). Code is single-use and valid 1 hour.")
print(f"\nCleanup when done:  delete student {sid} (cascades consents + exchange code).")
