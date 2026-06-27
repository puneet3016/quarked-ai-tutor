import sys
import os
import datetime
import uuid
from unittest.mock import MagicMock, patch

# Ensure backend directory is in the path
backend_path = '/Users/puneetsharma/Documents/quarked /quarked-ai-tutor/backend'
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_path, '.env'))

# Set dummy env vars if not present to pass startup checks during test imports
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-thirty-two-bytes-long-12345")
os.environ.setdefault("SERVER_API_KEY", "test-server-api-key")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("QUESTION_ENC_KEY", "aybYOvSqBtuOqAnwVbn5bGD7KkqJdsX6UmBnpOnDYcM=") # 32 bytes base64
os.environ.setdefault("OTP_PEPPER", "test-otp-pepper")
os.environ.setdefault("RESEND_API_KEY", "re_test_key")
os.environ.setdefault("OTP_FROM_EMAIL", "Quarked <consent@example.com>")
# Relaxed cookie settings so the TestClient (http://testserver) can store student_token
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("COOKIE_DOMAIN", "")

# Mock Gemini client
import gemini_client
mock_client = MagicMock()
gemini_client.client = mock_client
gemini_client.client.models.count_tokens.return_value = MagicMock(total_tokens=150)

def mock_generate_content(model, contents, config=None):
    resp = MagicMock()
    resp.usage_metadata = MagicMock(prompt_token_count=150, candidates_token_count=100)
    # config may be a GenerateContentConfig object OR a plain dict
    if config is None:
        schema = None
    elif isinstance(config, dict):
        schema = config.get('response_schema')
    else:
        schema = getattr(config, 'response_schema', None)
    schema_name = getattr(schema, '__name__', None)
    if schema_name == 'AskResult':
        resp.text = '{"answer": "Force equals mass times acceleration (F=ma).", "subject": "Physics", "topic": "Forces", "difficulty": "medium", "resolved": true}'
    elif schema_name == 'MarkResult':
        resp.text = '{"marks_awarded": 3, "marks_available": 3, "mark_breakdown": ["Correct formula"], "feedback": "Good job!", "model_answer": "F=ma"}'
    elif schema_name == 'QuestionSet':
        resp.text = '{"questions": [{"question": "Explain Newton\'s second law.", "mark_scheme": ["F=ma"], "marks_available": 3}]}'
    else:
        resp.text = '{}'
    return resp

gemini_client.client.models.generate_content.side_effect = mock_generate_content

# Mock parental OTP verification to bypass actual email/SMS/WhatsApp send/receive
import otp_service
otp_service.verify_otp = lambda challenge_id, code: (True, "parent@example.com")

# Import FastAPI TestClient and our application
from fastapi.testclient import TestClient
from main import app, SECRET_KEY, SERVER_API_KEY, ALGORITHM, _require
from jose import jwt
import supabase_client
import budget_guard

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {SERVER_API_KEY}"}

def test_startup_fail_fast():
    # Verify fail-fast logic raises error when a key is missing
    raised = False
    try:
        _require("NON_EXISTENT_ENV_KEY_12345")
    except RuntimeError:
        raised = True
    assert raised, "Expected _require to raise RuntimeError"

@patch("requests.post")
def test_consent_verification_and_withdrawal_flows(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    print("Starting Quarked compliance test suite...")
    sb = supabase_client.get_supabase()

    # 1. Clean up any previous test student
    try:
        res = sb.table('students').select('id').eq('name', 'Compliance Test Student').execute()
        for row in res.data:
            sb.table('students').delete().eq('id', row['id']).execute()
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    # 2. Test Student Onboarding (Staff Auth required)
    # Call without auth -> should be 401
    r = client.post("/students", json={})
    assert r.status_code == 401
    
    onboard_payload = {
        "name": "Compliance Test Student",
        "grade": "Year 11",
        "board": "IGCSE",
        "parent_name": "Test Parent",
        "parent_email": "parent@example.com",
        "parent_phone": "+919999999999",
        "is_minor": True
    }
    r = client.post("/students", json=onboard_payload, headers=auth_headers)
    assert r.status_code == 200, f"Onboarding failed: {r.text}"
    student = r.json()
    student_id = student['id']
    assert student['active'] is False, "New student must be inactive initially"

    # 3. Test OTP Spam Cooldown (Public endpoint)
    otp_payload = {
        "destination": "parent@example.com",
        "channel": "email"
    }
    r = client.post("/consent/otp", json=otp_payload)
    assert r.status_code == 200
    challenge_id = r.json()['challenge_id']

    # Submitting within 60s cooldown -> 429
    r_spam = client.post("/consent/otp", json=otp_payload)
    assert r_spam.status_code == 429

    # 4. Test Submit Consent (Public endpoint)
    consent_payload = {
        "student_id": student_id,
        "purposes": ["tutoring", "weak_topic_analytics"],
        "granted_by": "Test Parent",
        "challenge_id": challenge_id,
        "code": "123456",
        "channel": "email"
    }
    r = client.post("/consent", json=consent_payload)
    assert r.status_code == 200
    res_data = r.json()
    assert "exchange_code" in res_data
    exchange_code = res_data["exchange_code"]

    # Verify DB trigger flipped active = True
    student_db = supabase_client.get_student_by_id(student_id)
    assert student_db['active'] is True

    # 5. Test Exchange Code Handoff -> issues 90-day cookie
    r = client.post("/session/exchange", json={"exchange_code": exchange_code})
    assert r.status_code == 200
    assert "student_token" in client.cookies
    token_cookie = client.cookies["student_token"]

    # Decode and verify token properties
    payload = jwt.decode(token_cookie, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == student_id
    assert "jti" in payload
    assert payload["version"] == student_db.get("token_version", 1)

    # 6. Test Tutoring Chat (/ask) with token cookie
    chat_payload = {
        "messages": [
            {"role": "user", "content": "Explain Newton's second law."}
        ],
        "subject": "Physics",
        "exam_board": "IGCSE",
        "level": "Extended",
        "student_id": student_id
    }
    # No cookie -> 401 (clear the jar first; TestClient persists the exchange cookie)
    client.cookies.clear()
    r_unauth = client.post("/ask", json=chat_payload)
    assert r_unauth.status_code == 401

    # With cookie -> 200
    client.cookies["student_token"] = token_cookie
    r = client.post("/ask", json=chat_payload)
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "Force equals mass times acceleration (F=ma)."

    # 7. Test Practice Marking (/api/mark) with token cookie
    mark_payload = {
        "subject": "Physics",
        "exam_board": "IGCSE",
        "level": "Extended",
        "topic": "Forces",
        "question": "What is F?",
        "mark_scheme": ["F=ma"],
        "student_answer": "F=ma",
        "student_id": student_id
    }
    r = client.post("/api/mark", json=mark_payload)
    assert r.status_code == 200, r.text
    assert r.json()["marks_awarded"] == 3

    # Test student_id mismatch in /api/mark -> 403
    mismatch_payload = dict(mark_payload, student_id=str(uuid.uuid4()))
    r_mismatch = client.post("/api/mark", json=mismatch_payload)
    assert r_mismatch.status_code == 403

    # 8. Test Consent Withdrawal & Revocation
    withdraw_payload = {
        "student_id": student_id,
        "purpose": "tutoring",
        "granted_by": "Test Parent"
    }
    # Generate parent signed withdrawal token
    withdraw_token_payload = {
        "sub": student_id,
        "action": "withdraw",
        "purposes": ["tutoring"]
    }
    withdraw_token = jwt.encode(withdraw_token_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    # Parent-accessible call using query token -> 200
    r = client.post(f"/consent/withdraw?token={withdraw_token}", json=withdraw_payload)
    assert r.status_code == 200, r.text

    # Verify student.active flipped back to False
    student_db = supabase_client.get_student_by_id(student_id)
    assert student_db['active'] is False
    # Verify token version incremented in DB
    assert student_db.get("token_version", 1) > payload["version"]

    # Verify old cookie is immediately rejected (token version mismatch)
    r_revoked = client.post("/ask", json=chat_payload)
    assert r_revoked.status_code == 401

    # 9. Clean up student
    sb.table('students').delete().eq('id', student_id).execute()


@patch("requests.post")
def test_portal_registration_and_login_flows(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    print("Starting Quarked student portal compliance tests...")
    sb = supabase_client.get_supabase()
    
    # 1. Clean up any previous test student
    try:
        res = sb.table('students').select('id').eq('username', 'portal.test.student').execute()
        for row in res.data:
            sb.table('students').delete().eq('id', row['id']).execute()
    except Exception as e:
        print(f"Warning during cleanup: {e}")

    # 2. Portal Student Registration
    register_payload = {
        "name": "Portal Test Student",
        "grade": "Year 11",
        "board": "IGCSE",
        "parent_name": "Portal Test Parent",
        "parent_email": "portalparent@example.com",
        "parent_phone": "+919999999999",
        "username": "portal.test.student",
        "password": "portalpassword123"
    }
    
    r = client.post("/api/auth/register", json=register_payload)
    assert r.status_code == 200, f"Registration failed: {r.text}"
    reg_data = r.json()
    assert reg_data["status"] == "pending_consent"
    student_id = reg_data["student_id"]
    challenge_id = reg_data["challenge_id"]

    # Verify student is in DB and active is False
    student_db = supabase_client.get_student_by_id(student_id)
    assert student_db is not None
    assert student_db["active"] is False
    assert student_db["username"] == "portal.test.student"
    
    # Try duplicate registration -> should return 400
    r_dup = client.post("/api/auth/register", json=register_payload)
    assert r_dup.status_code == 400
    
    # 3. Test Student Login Prior to Parent Consent -> should return 403 pending_parent_consent
    login_payload = {
        "username": "portal.test.student",
        "password": "portalpassword123"
    }
    r_login = client.post("/api/auth/login", json=login_payload)
    assert r_login.status_code == 403, f"Expected 403 for inactive student: {r_login.text}"
    login_err = r_login.json()["detail"]
    assert login_err["error"] == "pending_parent_consent"
    assert login_err["student_id"] == student_id
    assert "challenge_id" in login_err

    # 4. Parent Verifies OTP via /api/consent
    consent_payload = {
        "student_id": student_id,
        "purposes": ["tutoring", "weak_topic_analytics"],
        "granted_by": "Portal Test Parent",
        "challenge_id": challenge_id,
        "code": "123456",
        "channel": "email"
    }
    with patch("otp_service.verify_otp", return_value=(True, "portalparent@example.com")):
        r_consent = client.post("/api/consent", json=consent_payload)
        assert r_consent.status_code == 200, f"Consent verification failed: {r_consent.text}"
        
    # Verify student active flips to True
    student_db = supabase_client.get_student_by_id(student_id)
    assert student_db["active"] is True

    # 5. Login After Consent -> should return 200 with Bearer token
    r_login_success = client.post("/api/auth/login", json=login_payload)
    assert r_login_success.status_code == 200, f"Login failed: {r_login_success.text}"
    login_data = r_login_success.json()
    assert "token" in login_data
    token = login_data["token"]

    # 6. Test Chat (/api/chat) with Bearer token in Authorization header
    chat_payload = {
        "messages": [
            {"role": "user", "content": "Explain gravity."}
        ],
        "subject": "Physics",
        "exam_board": "Cambridge IGCSE",
        "level": "Core"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    r_chat = client.post("/api/chat", json=chat_payload, headers=headers)
    assert r_chat.status_code == 200, f"Chat failed: {r_chat.text}"
    
    # 7. Test Practice Marking (/api/mark) with Bearer token
    mark_payload = {
        "subject": "Physics",
        "exam_board": "Cambridge IGCSE",
        "level": "Core",
        "topic": "Gravity",
        "question": "What is gravity?",
        "mark_scheme": ["attractive force"],
        "student_answer": "a force that attracts things",
        "student_id": student_id
    }
    r_mark = client.post("/api/mark", json=mark_payload, headers=headers)
    assert r_mark.status_code == 200, f"Marking failed: {r_mark.text}"

    # 8. Test /api/chat with invalid/expired/stale token -> falls back to GUEST (never 401)
    bad_headers = {"Authorization": "Bearer bad.token.here"}
    r_chat_bad = client.post("/api/chat", json=chat_payload, headers=bad_headers)
    assert r_chat_bad.status_code == 200, "Invalid token in /api/chat must fallback to guest and return 200"

    # 9. Consent Withdrawal & Immediate Revocation Check for Bearer token
    withdraw_payload = {
        "student_id": student_id,
        "purpose": "tutoring",
        "granted_by": "Portal Test Parent"
    }
    withdraw_token_payload = {
        "sub": student_id,
        "action": "withdraw",
        "purposes": ["tutoring"]
    }
    withdraw_token = jwt.encode(withdraw_token_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    r_withdraw = client.post(f"/api/consent/withdraw?token={withdraw_token}", json=withdraw_payload)
    assert r_withdraw.status_code == 200
    
    # Check that active flipped to False
    student_db = supabase_client.get_student_by_id(student_id)
    assert student_db["active"] is False

    # Check that subsequent call to /api/mark with old token is BLOCKED (401 due to revoked version)
    r_mark_revoked = client.post("/api/mark", json=mark_payload, headers=headers)
    assert r_mark_revoked.status_code == 401

    # 10. Clean up student
    sb.table('students').delete().eq('id', student_id).execute()


if __name__ == "__main__":
    test_startup_fail_fast()
    try:
        test_consent_verification_and_withdrawal_flows()
        test_portal_registration_and_login_flows()
        print("\nAll compliance and portal reconciliation tests passed successfully!")
    except AssertionError as e:
        print(f"\nAssertion error during compliance test: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during compliance test: {e}")
        sys.exit(1)
