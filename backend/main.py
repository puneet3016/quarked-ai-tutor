from fastapi import FastAPI, HTTPException, Request, Depends, Response, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json
import os
import uuid
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from dotenv import load_dotenv
from collections import defaultdict
from typing import Literal

from prompts import get_system_prompt
from gemini_client import get_tutor_response_stream, generate_practice_questions, mark_student_answer, MODEL
from exam_data import SUBJECT_LEVELS, get_levels_for_subject, get_subjects_for_board
from supabase_client import (
    verify_supabase_jwt, get_student_by_id, create_student,
    get_students_list, save_consent, get_consents_for_student,
    get_consent_events, create_session, log_interaction,
    get_admin_dashboard_data, get_student_interactions, get_supabase
)

load_dotenv()

app = FastAPI(title="Quarked AI Tutor Backend")
security = HTTPBearer()

# Password verification for compatibility admin login
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.environ.get("JWT_SECRET", "super-secret-default-key-please-change-in-prod")
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

@app.on_event("startup")
async def startup():
    print("Quarked AI Tutor backend started (Schema v2 active)")

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
    student_id: str | None = None

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
    parent_email: str
    parent_phone: str | None = None
    is_minor: bool = True

class ConsentRequest(BaseModel):
    purpose: str
    status: str
    granted_by: str
    verify_method: str = "otp"
    verify_ref: str | None = None

class AuthRequest(BaseModel):
    username: str
    password: str


# --- Auth Middleware (Staff Only) ---
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency that verifies tutor/staff authentication using either local Admin JWT or Supabase JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 1. Try local JWT decode (compatibility for admin login)
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username == "admin":
            return {"id": "admin", "username": "admin", "is_admin": True}
    except Exception:
        pass

    # 2. Fallback to Supabase Auth JWT verification
    user = verify_supabase_jwt(credentials.credentials)
    if user is None:
        raise credentials_exception
    return {"id": user.id, "email": user.email, "username": user.email, "is_admin": True}

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """In beta, any authenticated staff member is authorized."""
    return current_user


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

@app.post("/api/students")
async def register_student(request: StudentCreateRequest, current_user = Depends(get_current_user)):
    managed_by = None
    try:
        # Check if the user ID is a valid UUID (Supabase Auth ID)
        uuid.UUID(current_user["id"])
        managed_by = current_user["id"]
    except ValueError:
        # Local admin has "admin" as ID, set managed_by to None to avoid foreign key error
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

@app.get("/api/students")
async def list_students(current_user = Depends(get_current_user)):
    return get_students_list()

@app.post("/api/students/{student_id}/consent")
async def add_student_consent(student_id: str, request: ConsentRequest, current_user = Depends(get_current_user)):
    student = get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    consent_data = {
        "student_id": student_id,
        "purpose": request.purpose,
        "status": request.status,
        "granted_by": request.granted_by.strip(),
        "verify_method": request.verify_method,
        "verify_ref": request.verify_ref
    }
    
    # Check if withdrawing
    if request.status == "withdrawn":
        consent_data["withdrawn_at"] = datetime.utcnow().isoformat()
        
    result = save_consent(consent_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to save consent record")
    return result

@app.get("/api/students/{student_id}/consents")
async def get_consents(student_id: str, current_user = Depends(get_current_user)):
    return get_consents_for_student(student_id)

@app.get("/api/students/{student_id}/events")
async def get_consent_audit_trail(student_id: str, current_user = Depends(get_current_user)):
    return get_consent_events(student_id)


# --- Admin Dashboard ---
@app.get("/api/admin/dashboard")
async def admin_dashboard(current_user = Depends(get_current_user)):
    return get_admin_dashboard_data()


# --- Chat & AI Endpoints ---

def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    input_rate = 0.10 / 1_000_000
    output_rate = 0.40 / 1_000_000
    if "3.5" in model_name:
        input_rate = 1.50 / 1_000_000
        output_rate = 9.00 / 1_000_000
    elif "1.5" in model_name:
        input_rate = 0.35 / 1_000_000
        output_rate = 1.50 / 1_000_000
    return (input_tokens * input_rate) + (output_tokens * output_rate)

async def classify_and_log_interaction(
    session_id: str, 
    student_id: str, 
    model: str, 
    question_text: str, 
    response_text: str, 
    subject: str, 
    exam_board: str, 
    level: str
):
    """Background task to run a fast classification of the exchange and log the billing/interaction."""
    try:
        from gemini_client import client
        
        classification_prompt = f"""You are an educational analytics classifier. Analyze this tutor-student exchange.
        
        STUDENT QUESTION: {question_text}
        TUTOR RESPONSE: {response_text}
        
        Identify:
        - Topic (e.g., 'Quadratic equations', 'Linear momentum', 'Photosynthesis')
        - Difficulty of the question ('easy', 'medium', 'hard')
        - Resolved: whether the tutor successfully resolved the student's doubt or if the student's doubt is fully answered (true/false)
        
        Respond ONLY with a JSON object matching this schema:
        {{
            "topic": "string",
            "difficulty": "easy" | "medium" | "hard",
            "resolved": true | false
        }}
        """
        
        class ClassificationResult(BaseModel):
            topic: str
            difficulty: Literal["easy", "medium", "hard"]
            resolved: bool

        input_tokens = (2500 + len(question_text) + len(response_text)) // 4
        output_tokens = len(response_text) // 4
        cost = estimate_cost(model, input_tokens, output_tokens)

        try:
            resp = client.models.generate_content(
                model=model,
                contents=classification_prompt,
                config={'response_mime_type': 'application/json', 'response_schema': ClassificationResult}
            )
            result = ClassificationResult.model_validate_json(resp.text)
            topic = result.topic
            difficulty = result.difficulty
            resolved = result.resolved
        except Exception as ex:
            print(f"Warning: Gemini classification failed: {ex}. Falling back to default values.")
            topic = "General Chat"
            difficulty = "medium"
            resolved = True
            
        log_interaction({
            "session_id": session_id,
            "student_id": student_id,
            "subject": subject,
            "topic": topic,
            "difficulty": difficulty,
            "resolved": resolved,
            "question_text": question_text,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost
        })
    except Exception as e:
        print(f"Error in classify_and_log_interaction background task: {e}")


@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request, background_tasks: BackgroundTasks):
    # 1. Gating & Verification
    if request.student_id:
        student = get_student_by_id(request.student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student record not found")
        if not student.get('active'):
            raise HTTPException(status_code=403, detail="Student is pending tutoring consent by parent.")
    else:
        # Rate limit unauthenticated (public widget) users
        client_ip = req.headers.get("x-forwarded-for", req.client.host).split(",")[0].strip()
        if not check_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail="You've used your 5 free questions for today! Please register at the portal."
            )
        increment_rate_limit(client_ip)

    # 2. History Cost Optimization (slice to last 10 messages)
    history_msgs = request.messages[:-1]
    if len(history_msgs) > 10:
        history_msgs = history_msgs[-10:]
    history = [{"role": m.role, "content": m.content} for m in history_msgs]
    current_message = request.messages[-1].content

    system_prompt = get_system_prompt(request.subject, request.exam_board, request.level)

    # 3. Create or Validate Session (if student is active)
    session_id = request.session_id
    if request.student_id:
        if not session_id:
            session_id = str(uuid.uuid4())
        try:
            sb = get_supabase()
            sess_check = sb.table('sessions').select('id').eq('id', session_id).execute()
            if not sess_check.data:
                create_session(request.student_id, MODEL)
        except Exception:
            create_session(request.student_id, MODEL)

    async def generate():
        try:
            latest_image = request.messages[-1].image
            stream = get_tutor_response_stream(
                current_message, history, system_prompt, 
                request.subject, request.exam_board, request.level, 
                latest_image
            )
            
            full_response = ""
            for chunk in stream:
                full_response += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"
                
            # Log the exchange in the background if it was an active student
            if request.student_id and session_id:
                background_tasks.add_task(
                    classify_and_log_interaction,
                    session_id, request.student_id, MODEL, current_message, full_response,
                    request.subject, request.exam_board, request.level
                )
                
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/generate")
async def generate_questions(request: GenerateRequest, current_user = Depends(get_current_user)):
    try:
        qs = generate_practice_questions(
            request.subject, request.topic, request.exam_board, request.level, request.num_questions
        )
        return qs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mark")
async def mark_answer(request: MarkRequest, background_tasks: BackgroundTasks):
    try:
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
            feedback_desc = f"Marks: {result.marks_awarded}/{result.marks_available}\nFeedback: {result.feedback}"
            
            background_tasks.add_task(
                classify_and_log_interaction,
                session_id, request.student_id, MODEL, question_desc, feedback_desc,
                request.subject, request.exam_board, request.level
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
    """Return available subjects and their levels for a board."""
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
