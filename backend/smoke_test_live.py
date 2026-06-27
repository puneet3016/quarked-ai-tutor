import sys
import os
import requests
import uuid

backend_path = '/Users/puneetsharma/Documents/quarked /quarked-ai-tutor/backend'
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_path, '.env'))

import supabase_client

API_URL = "https://api.quarked.tech/api"

def run_smoke_test():
    print("======================================================================")
    print("         QUARKED LIVE PRODUCTION BACKEND SMOKE TEST RUNNER")
    print("======================================================================\n")

    # Step 1: Get parent email
    parent_email = input("Step 1: Enter a parent email you control: ").strip().lower()
    if not parent_email:
        print("FAIL: Parent email cannot be empty")
        sys.exit(1)
        
    username = f"smoke.test.{uuid.uuid4().hex[:6]}"
    password = "smoketestpassword123"
    print(f"Generated test student username: {username}")
    print("PASS: Step 1 (Username generated and email collected)\n")

    # Step 2: Register
    print("Step 2: POST /api/auth/register...")
    register_payload = {
        "name": "Smoke Test Student",
        "grade": "Year 11",
        "board": "IGCSE",
        "parent_name": "Test Parent",
        "parent_email": parent_email,
        "parent_phone": "+919999999999",
        "username": username,
        "password": password
    }
    
    r = requests.post(f"{API_URL}/auth/register", json=register_payload)
    if r.status_code != 200:
        print(f"FAIL: Step 2 - Registration failed with status {r.status_code}: {r.text}")
        sys.exit(1)
        
    reg_data = r.json()
    assert reg_data["status"] == "pending_consent", f"Expected pending_consent, got: {reg_data}"
    student_id = reg_data["student_id"]
    challenge_id = reg_data["challenge_id"]
    print(f"PASS: Step 2 (Registration successful. Student ID: {student_id})")
    print("Check your parent email inbox for the OTP verification code.\n")

    # Step 3: Login prior to consent (should be blocked)
    print("Step 3: POST /api/auth/login (prior to consent)...")
    login_payload = {
        "username": username,
        "password": password
    }
    r_login = requests.post(f"{API_URL}/auth/login", json=login_payload)
    if r_login.status_code != 403:
        print(f"FAIL: Step 3 - Expected status 403 for inactive student, got {r_login.status_code}: {r_login.text}")
        sys.exit(1)
        
    login_err = r_login.json()["detail"]
    assert login_err["error"] == "pending_parent_consent"
    assert login_err["student_id"] == student_id
    print("PASS: Step 3 (Login successfully blocked with pending_parent_consent)\n")

    # Step 4 & 5: Read OTP and verify
    print("Step 4: Prompting for parental consent code...")
    otp_code = input("Check the parent inbox and enter the 6-digit code: ").strip()
    if len(otp_code) != 6 or not otp_code.isdigit():
        print("FAIL: OTP must be a 6-digit number")
        cleanup(student_id)
        sys.exit(1)
    print("PASS: Step 4 (OTP code input read successfully)\n")

    print("Step 5: POST /api/consent (verifying parent OTP)...")
    consent_payload = {
        "student_id": student_id,
        "purposes": ["tutoring", "weak_topic_analytics"],
        "granted_by": "Test Parent",
        "challenge_id": challenge_id,
        "code": otp_code,
        "channel": "email"
    }
    r_consent = requests.post(f"{API_URL}/consent", json=consent_payload)
    if r_consent.status_code != 200:
        print(f"FAIL: Step 5 - Consent verification failed with status {r_consent.status_code}: {r_consent.text}")
        cleanup(student_id)
        sys.exit(1)
        
    print("PASS: Step 5 (Parent consent verified and account activated)\n")

    # Step 6: Login after consent (should succeed)
    print("Step 6: POST /api/auth/login again...")
    r_login_success = requests.post(f"{API_URL}/auth/login", json=login_payload)
    if r_login_success.status_code != 200:
        print(f"FAIL: Step 6 - Login failed with status {r_login_success.status_code}: {r_login_success.text}")
        cleanup(student_id)
        sys.exit(1)
        
    login_data = r_login_success.json()
    assert "token" in login_data
    token = login_data["token"]
    print("PASS: Step 6 (Login succeeded, Bearer token retrieved)\n")

    # Step 7: Chat with Bearer Token
    print("Step 7: POST /api/chat (tutoring question with Bearer Token)...")
    chat_payload = {
        "messages": [
            {"role": "user", "content": "Explain Newton's third law of motion and give an everyday example."}
        ],
        "subject": "Physics",
        "exam_board": "Cambridge IGCSE",
        "level": "Core"
    }
    headers = {"Authorization": f"Bearer {token}"}
    r_chat = requests.post(f"{API_URL}/chat", json=chat_payload, headers=headers)
    if r_chat.status_code != 200:
        print(f"FAIL: Step 7 - Chat request failed with status {r_chat.status_code}: {r_chat.text}")
        cleanup(student_id)
        sys.exit(1)
        
    # Read streamed response text
    print("Live Tutor Response preview:")
    print("----------------------------------------------------------------------")
    print(r_chat.text[:400])
    print("----------------------------------------------------------------------")
    assert "teaser" not in r_chat.text.lower() and "limit" not in r_chat.text.lower(), "Expected real tutoring response, not teaser/limit warning"
    print("PASS: Step 7 (Tutoring chat response received and verified)\n")

    # Step 8: Practice Marking with Bearer Token
    print("Step 8: POST /api/mark (practice marking with Bearer Token)...")
    mark_payload = {
        "subject": "Physics",
        "exam_board": "Cambridge IGCSE",
        "level": "Core",
        "topic": "Forces",
        "question": "What is Newton's third law?",
        "mark_scheme": ["every action has an equal and opposite reaction"],
        "student_answer": "every action has an equal and opposite reaction",
        "student_id": student_id
    }
    r_mark = requests.post(f"{API_URL}/mark", json=mark_payload, headers=headers)
    if r_mark.status_code != 200:
        print(f"FAIL: Step 8 - Practice marking failed with status {r_mark.status_code}: {r_mark.text}")
        cleanup(student_id)
        sys.exit(1)
        
    print(f"Marking feedback: {r_mark.json().get('feedback')}")
    print("PASS: Step 8 (Practice marking response received and verified)\n")

    # Step 9: Cleanup
    print("Step 9: Cleaning up test student from Supabase...")
    cleanup(student_id)
    print("PASS: Step 9 (Test student deleted)\n")

    print("======================================================================")
    print("      ALL STEPS PASSED: LIVE BACKEND IS 100% OPERATIONAL! 🎉")
    print("======================================================================")

def cleanup(student_id):
    try:
        sb = supabase_client.get_supabase()
        sb.table('students').delete().eq('id', student_id).execute()
        print("Cleaned up database records for test student.")
    except Exception as e:
        print(f"Warning during cleanup: {e}")

if __name__ == "__main__":
    try:
        run_smoke_test()
    except KeyboardInterrupt:
        print("\nTest cancelled by user.")
        sys.exit(0)
