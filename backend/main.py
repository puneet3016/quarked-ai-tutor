from fastapi import FastAPI, HTTPException, Request, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import json
import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from dotenv import load_dotenv
from collections import defaultdict
from typing import Literal

from prompts import get_system_prompt
from gemini_client import get_tutor_response_stream, generate_practice_questions, mark_student_answer, client
from exam_data import SUBJECT_LEVELS, get_levels_for_subject, get_subjects_for_board
from supabase_client import (
    verify_supabase_jwt, get_student_by_id, create_student,
    get_students_list, save_consent, get_consents_for_student,
    get_consent_events, create_session,
    get_admin_dashboard_data, get_student_interactions, get_supabase
)
import budget_guard
from budget_guard import MODEL

load_dotenv()

app = FastAPI(title="Quarked AI Tutor Backend")
security = HTTPBearer()

# Password verification for compatibility admin login
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"{name} is required but missing from environment variables.")
    return v

SECRET_KEY = _require("SECRET_KEY")
SERVER_API_KEY = _require("SERVER_API_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

# Admin hash generated for 'puneetteenukrisha3055@&*'
ADMIN_PASSWORD_HASH = "$2b$12$T1xohQQ3LwPwB2r726siMe1UK32kWj40T19xOzn53pcOeq2hQHJne"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Rate limiting for public widget (unregistered / unauthenticated users)
PUBLIC_RATE_LIMIT = 5  # max questions per IP per day
rate_limit_store = defaultdict(lambda: {"count": 0, "date": datetime.utcnow().date()})

def check_rate_limit(ip: str) -> bool:
    """Returns True if the IP is within the daily limit, False if exceeded."""
    entry = rate_limit_store[ip]
    today = datetime.utcnow().date()
    if entry["date"] != today:
        entry["count"] = 0
        entry["date"] = today
    return entry["count"] < PUBLIC_RATE_LIMIT

def increment_rate_limit(ip: str):
    entry = rate_limit_store[ip]
    today = datetime.utcnow().date()
    if entry["date"] != today:
        entry["count"] = 1
        entry["date"] = today
    else:
        entry["count"] += 1


async def schedule_90_day_retention_purge():
    """Runs a background loop every 24 hours to purge question texts older than 90 days."""
    while True:
        try:
            print("Running 90-day data retention purge job...")
            sb = get_supabase()
            cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()
            
            # Nullify interactions older than 90 days
            res = sb.table("interactions").update({"question_text": None}).lt("created_at", cutoff).not_.is_("question_text", "null").execute()
            if res.data:
                print(f"Purge complete: Nullified {len(res.data)} interactions older than 90 days.")
        except Exception as e:
            print(f"Error in data retention purge job: {e}")
            
        await asyncio.sleep(86400)


@app.on_event("startup")
async def startup():
    print(f"Quarked AI Tutor backend started (Schema v2 active | Model: {MODEL})")
    # Start 90-day retention loop in the background
    asyncio.create_task(schedule_90_day_retention_purge())


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.quarked.tech",
        "https://quarked.tech",
        "https://neon-pithivier-55f97b.netlify.app",
        "http://localhost:5173",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request Models ---
class ChatMessage(BaseModel):
    role: str
    content: str
    image: str | None = None
    
class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    subject: str
    exam_board: str
    level: str
    session_id: str | None = None
    student_id: str

class GenerateRequest(BaseModel):
    subject: str
    topic: str
    exam_board: str
    level: str
    num_questions: int = 3

class MarkRequest(BaseModel):
    subject: str
    exam_board: str
    level: str
    topic: str
    question: str
    mark_scheme: list[str]
    student_answer: str
    student_id: str | None = None

class StudentCreateRequest(BaseModel):
    name: str
    grade: str | None = None
    board: str
    parent_name: str
    parent_email: EmailStr
    parent_phone: str | None = None
    is_minor: bool = True

class ConsentSubmitRequest(BaseModel):
    student_id: str
    purposes: list[str]
    granted_by: str
    challenge_id: str
    code: str
    channel: str = "email"

class ConsentWithdrawRequest(BaseModel):
    student_id: str
    purpose: str
    granted_by: str
    verify_method: str = "manual"

class OtpRequest(BaseModel):
    destination: str
    channel: str = "email"

class AuthRequest(BaseModel):
    username: str
    password: str


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency that verifies tutor/staff authentication using either SERVER_API_KEY, local Admin JWT, or Supabase JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    if token == SERVER_API_KEY:
        return {"id": "server", "username": "server", "is_admin": True}
    
    # 1. Try local JWT decode (compatibility for admin login)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username == "admin":
            return {"id": "admin", "username": "admin", "is_admin": True}
    except Exception:
        pass

    # 2. Fallback to Supabase Auth JWT verification
    user = verify_supabase_jwt(token)
    if user is None:
        raise credentials_exception
    return {"id": user.id, "email": user.email, "username": user.email, "is_admin": True}

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """In beta, any authenticated staff member is authorized."""
    return current_user


def _hash_code(code: str) -> str:
    import hmac
    import hashlib
    pepper = os.getenv("OTP_PEPPER")
    if not pepper:
        raise RuntimeError("OTP_PEPPER is required but missing from environment.")
    return hmac.new(pepper.encode(), code.encode(), hashlib.sha256).hexdigest()


async def get_student_from_cookie(request: Request, response: Response):
    """
    Dependency to authenticate the student from the httpOnly secure cookie.
    Validates token signature, expiration, jti, and live database consent check.
    Implements silent auto-renewal if the token is within 30 days of expiry.
    """
    token = request.cookies.get("student_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing student token cookie"
        )
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        student_id = payload.get("sub")
        jti = payload.get("jti")
        token_ver = payload.get("version", 1)
        exp = payload.get("exp")
        
        if not student_id or not jti or not exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims"
            )
            
        # Re-check live consent status
        budget_guard.require_consent(str(student_id), "tutoring")
        
        # Retrieve student to check token version revocation
        student = get_student_by_id(str(student_id))
        if not student:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Student not found"
            )
            
        # Revocation check via version
        current_ver = student.get("token_version", 1)
        if token_ver < current_ver:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
            
        # Silent auto-renewal: renew only when within 30 days of expiry
        # 30 days in seconds = 30 * 24 * 3600 = 2592000
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if exp - now_ts < 2592000:
            new_jti = str(uuid.uuid4())
            new_payload = {
                "sub": student_id,
                "iat": now_ts,
                "exp": now_ts + (90 * 24 * 3600),
                "jti": new_jti,
                "version": current_ver
            }
            new_token = jwt.encode(new_payload, SECRET_KEY, algorithm=ALGORITHM)
            response.set_cookie(
                key="student_token",
                value=new_token,
                httponly=True,
                secure=True,
                samesite="none",
                domain=".quarked.tech",
                max_age=90 * 24 * 3600
            )
            
        return student
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid student token: {str(e)}"
        )


async def get_any_auth(request: Request, response: Response, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Allows staff (Supabase JWT/Admin JWT/Server API Key) or students (signed student JWT)."""
    # 1. Try staff auth
    try:
        user = await get_current_user(credentials)
        if user:
            return {"type": "staff", "user": user}
    except Exception:
        pass
        
    # 2. Try student token cookie
    try:
        student = await get_student_from_cookie(request, response)
        if student:
            return {"type": "student", "student": student}
    except Exception:
        pass
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized access",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_withdrawal_auth(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies that the caller is authorized to withdraw consent.
    Accepts:
    1. A valid staff credential (get_current_user).
    2. A token passed in query parameter or request body signed with SECRET_KEY.
    """
    # 1. Try staff auth
    try:
        user = await get_current_user(credentials)
        if user:
            return {"type": "staff", "user": user}
    except Exception:
        pass
        
    # 2. Try signed withdraw token from query parameters or request body
    token = request.query_params.get("token")
    if not token:
        try:
            body = await request.json()
            token = body.get("token")
        except Exception:
            pass
            
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            action = payload.get("action")
            student_id = payload.get("sub")
            if action == "withdraw" and student_id:
                return {"type": "parent", "student_id": student_id}
        except Exception:
            pass
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized to withdraw consent"
    )


# --- Compatibility Auth Endpoint ---
@app.post("/api/auth/login")
async def login(request: AuthRequest):
    username = request.username.lower().strip()
    if username != "admin":
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not pwd_context.verify(request.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    access_token = create_access_token(data={"sub": "admin"})
    
    return {
        "token": access_token,
        "student": {
            "name": "Puneet Sharma",
            "username": "admin",
            "isAdmin": True,
            "uuid": "admin"
        },
        "session_id": str(uuid.uuid4())
    }


# --- Student Management Endpoints (Staff Only) ---

@app.post("/students")
async def onboard_student(request: StudentCreateRequest, current_user = Depends(get_current_user)):
    managed_by = None
    try:
        uuid.UUID(current_user["id"])
        managed_by = current_user["id"]
    except ValueError:
        pass

    student_data = {
        "name": request.name.strip(),
        "grade": request.grade,
        "board": request.board,
        "parent_name": request.parent_name.strip(),
        "parent_email": request.parent_email.lower().strip(),
        "parent_phone": request.parent_phone,
        "is_minor": request.is_minor,
        "active": False,
        "managed_by": managed_by
    }
    result = create_student(student_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create student record")
    return result

@app.get("/students")
async def list_students(current_user = Depends(get_current_user)):
    return get_students_list()

@app.get("/students/{id}/events")
async def get_consent_audit_trail(id: str, current_user = Depends(get_current_user)):
    return get_consent_events(id)


# --- Parent Consent Endpoints ---

@app.post("/consent/otp")
async def send_consent_otp(request: OtpRequest):
    from otp_service import request_otp, OtpCooldownError
    try:
        challenge_id = request_otp(request.destination.strip().lower(), request.channel)
        return {"challenge_id": challenge_id}
    except OtpCooldownError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP code: {str(e)}")

@app.post("/consent")
async def submit_consent(request: ConsentSubmitRequest):
    from otp_service import verify_otp, send_withdrawal_email
    
    # 1. Verify OTP
    ok, destination = verify_otp(request.challenge_id, request.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    # 2. Write consents rows (DB triggers sync active flag + log consent events)
    for purpose in request.purposes:
        consent_data = {
            "student_id": request.student_id,
            "purpose": purpose,
            "status": "granted",
            "granted_by": request.granted_by.strip(),
            "verify_method": request.channel,
            "verify_ref": request.challenge_id
        }
        save_consent(consent_data)
        
    # 3. Generate signed withdrawal token & email withdrawal link to the parent
    try:
        withdraw_payload = {
            "sub": request.student_id,
            "action": "withdraw",
            "purposes": request.purposes
        }
        # Parents have no logins, so we sign a JWT without expiration to allow manual withdrawal
        withdraw_token = jwt.encode(withdraw_payload, SECRET_KEY, algorithm=ALGORITHM)
        withdraw_link = f"https://app.quarked.tech/withdraw-consent?token={withdraw_token}"
        
        student = get_student_by_id(request.student_id)
        student_name = student["name"] if student else "your student"
        send_withdrawal_email(destination, student_name, withdraw_link)
    except Exception as e:
        print(f"Error sending withdrawal email: {e}")
        
    # 4. Generate short-lived exchange code
    raw_exchange_code = str(uuid.uuid4())
    hashed_code = _hash_code(raw_exchange_code)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    
    try:
        sb = get_supabase()
        sb.table("exchange_codes").insert({
            "student_id": request.student_id,
            "code_hash": hashed_code,
            "expires_at": expires_at
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record exchange code: {e}")
        
    return {"message": "Consent recorded successfully", "exchange_code": raw_exchange_code}


class ExchangeRequest(BaseModel):
    exchange_code: str


@app.post("/session/exchange")
async def session_exchange(request: ExchangeRequest, response: Response):
    sb = get_supabase()
    hashed = _hash_code(request.exchange_code)
    
    # Query database for unconsumed, unexpired exchange code
    now_str = datetime.now(timezone.utc).isoformat()
    res = sb.table("exchange_codes").select("*").eq("code_hash", hashed).is_("consumed_at", "null").execute()
    
    if not res.data:
        raise HTTPException(status_code=400, detail="Invalid or already used exchange code")
        
    code_record = res.data[0]
    if datetime.fromisoformat(code_record["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Exchange code has expired")
        
    student_id = code_record["student_id"]
    
    # Mark as consumed
    sb.table("exchange_codes").update({"consumed_at": now_str}).eq("id", code_record["id"]).execute()
    
    # Fetch student to get current token version
    student = get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    current_ver = student.get("token_version", 1)
    
    # Mint a fresh 90-day student token cookie
    now_ts = int(datetime.now(timezone.utc).timestamp())
    new_payload = {
        "sub": student_id,
        "iat": now_ts,
        "exp": now_ts + (90 * 24 * 3600),
        "jti": str(uuid.uuid4()),
        "version": current_ver
    }
    student_token = jwt.encode(new_payload, SECRET_KEY, algorithm=ALGORITHM)
    
    response.set_cookie(
        key="student_token",
        value=student_token,
        httponly=True,
        secure=True,
        samesite="none",
        domain=".quarked.tech",
        max_age=90 * 24 * 3600
    )
    
    return {"message": "Session established successfully"}


@app.post("/consent/withdraw")
async def withdraw_consent(request: ConsentWithdrawRequest, auth = Depends(get_withdrawal_auth)):
    if auth["type"] == "parent":
        if str(request.student_id) != str(auth["student_id"]):
            raise HTTPException(status_code=403, detail="student_id mismatch in withdrawal token")
            
    consent_data = {
        "student_id": request.student_id,
        "purpose": request.purpose,
        "status": "withdrawn",
        "granted_by": request.granted_by.strip(),
        "verify_method": request.verify_method,
        "withdrawn_at": datetime.utcnow().isoformat()
    }
    result = save_consent(consent_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to withdraw consent")
        
    # Revocation: increment students.token_version whenever a parent withdraws consent
    try:
        sb = get_supabase()
        student = get_student_by_id(request.student_id)
        if student:
            current_ver = student.get("token_version", 1)
            sb.table("students").update({"token_version": current_ver + 1}).eq("id", request.student_id).execute()
    except Exception as e:
        print(f"Error incrementing token version: {e}")
        
    return {"message": f"Consent for '{request.purpose}' withdrawn successfully"}


# --- Admin Dashboard ---
@app.get("/api/admin/dashboard")
async def admin_dashboard(current_user = Depends(get_current_user)):
    return get_admin_dashboard_data()


# --- Tutoring Chat Endpoint (Exact compliant flow) ---

class AskResult(BaseModel):
    answer: str
    subject: str
    topic: str
    difficulty: Literal["easy", "medium", "hard"]
    resolved: bool

@app.post("/ask")
async def ask(request: ChatRequest, student = Depends(get_student_from_cookie)):
    from google.genai import types
    
    # Verify client-supplied student_id matches token
    if str(request.student_id) != str(student["id"]):
        raise HTTPException(status_code=403, detail="student_id mismatch")
    
    # Step 2: check_student_daily_cap(student_id)
    budget_guard.check_student_daily_cap(request.student_id)
    
    # Cost control: cap chat history to the last 8-10 turns (approx 16 messages)
    history_msgs = request.messages[:-1]
    if len(history_msgs) > 16:
        history_msgs = history_msgs[-16:]
        
    # Build contents for counting and generating
    system_prompt = get_system_prompt(request.subject, request.exam_board, request.level)
    
    contents = []
    for m in history_msgs:
        role = 'user' if m.role == 'user' else 'model'
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
        
    current_message = request.messages[-1].content
    contents.append(types.Content(role='user', parts=[types.Part.from_text(text=current_message)]))
    
    # Step 3: Count input tokens with the GenAI SDK
    try:
        token_resp = client.models.count_tokens(
            model=MODEL,
            contents=contents
        )
        # Add system prompt token overhead approximation (2500 tokens)
        estimated_input_tokens = token_resp.total_tokens + 2500
    except Exception as e:
        print(f"Error counting tokens: {e}")
        estimated_input_tokens = (2500 + len(current_message) + sum(len(m.content) for m in history_msgs)) // 4

    # Check monthly budget -> 429 if over cap
    budget_guard.check_budget(estimated_input_tokens)
    
    # Step 4: Call Gemini with max_output_tokens from config
    # Step 6: Return answer AND structured tags in one single JSON response
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.3,
        max_output_tokens=budget_guard.MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        response_schema=AskResult
    )
    
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config
        )
        
        # Step 5: Read real usage_metadata
        input_tokens = resp.usage_metadata.prompt_token_count
        output_tokens = resp.usage_metadata.candidates_token_count
        
        # Parse JSON output
        result = AskResult.model_validate_json(resp.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API execution failed: {str(e)}")
        
    # Step 7: log_interaction(...)
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        
    try:
        sb = get_supabase()
        sess_check = sb.table('sessions').select('id').eq('id', session_id).execute()
        if not sess_check.data:
            create_session(request.student_id, MODEL)
    except Exception:
        create_session(request.student_id, MODEL)
        
    budget_guard.log_interaction(
        session_id=session_id,
        student_id=request.student_id,
        model=MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        subject=request.subject,
        topic=result.topic,
        difficulty=result.difficulty,
        resolved=result.resolved,
        question_text=current_message
    )
    
    return result.model_dump()


# --- Practice Generation & Mark Endpoints (Updated) ---
@app.post("/api/generate")
async def generate_questions(request: GenerateRequest, current_user = Depends(get_current_user)):
    try:
        # Enforce monthly budget check for practice question generation (estimated 200 tokens)
        budget_guard.check_budget(estimated_input_tokens=200)
        
        qs = generate_practice_questions(
            request.subject, request.topic, request.exam_board, request.level, request.num_questions
        )
        return qs.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mark")
async def mark_answer(request: MarkRequest, student = Depends(get_student_from_cookie)):
    # Verify student_id in token matches body
    if request.student_id:
        if str(request.student_id) != str(student["id"]):
            raise HTTPException(status_code=403, detail="student_id mismatch")
    else:
        request.student_id = str(student["id"])

    try:
        # Enforce monthly budget check for practice marking (estimated 1000 tokens)
        budget_guard.check_budget(estimated_input_tokens=1000)
        
        result = mark_student_answer(
            request.question, request.mark_scheme, request.student_answer, request.subject, request.exam_board
        )
        
        # Log to interactions if student is provided
        if request.student_id:
            session_id = str(uuid.uuid4())
            try:
                create_session(request.student_id, MODEL)
            except Exception:
                pass
                
            question_desc = f"Practice Question: {request.question}\nStudent Answer: {request.student_answer}"
            
            budget_guard.log_interaction(
                session_id=session_id,
                student_id=request.student_id,
                model=MODEL,
                input_tokens=100,
                output_tokens=100,
                subject=request.subject,
                topic=request.topic,
                difficulty="medium",
                resolved=True,
                question_text=question_desc
            )
            
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress")
async def get_progress(student_id: str, current_user = Depends(get_current_user)):
    history = get_student_interactions(student_id)
    return {"history": history}

@app.get("/api/subjects/{exam_board}")
async def get_subjects(exam_board: str):
    subjects = get_subjects_for_board(exam_board)
    result = {}
    for subject in subjects:
        result[subject] = get_levels_for_subject(subject, exam_board)
    return result


# Serve the widget
@app.get("/widget/widget.js")
async def serve_widget():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    widget_path = os.path.join(base_dir, "widget", "widget.js")
    if os.path.exists(widget_path):
        return FileResponse(widget_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Widget script not found")
    
@app.get("/widget/widget-loader.js")
async def serve_widget_loader():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    widget_path = os.path.join(base_dir, "widget", "widget-loader.js")
    if os.path.exists(widget_path):
        return FileResponse(widget_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Widget loader not found")
