from fastapi import FastAPI, HTTPException, Request, Depends, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import json
import os
import uuid
from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv

from prompts import get_system_prompt
from gemini_client import get_tutor_response_stream, generate_practice_questions, mark_student_answer, initialize_caches
from supabase_client import (
    log_conversation, save_practice_result, get_practice_history, 
    get_student_by_username, verify_password, get_password_hash, 
    create_student, approve_student_in_db, log_session_action,
    get_admin_dashboard_data
)

load_dotenv()

# JWT Config
SECRET_KEY = os.environ.get("JWT_SECRET", "super-secret-default-key-please-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

app = FastAPI(title="Quarked AI Tutor Backend")
security = HTTPBearer()

@app.on_event("startup")
async def startup():
    initialize_caches()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.quarked.tech",
        "https://quarked.tech",
        "http://localhost:5173",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
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
    student_id: str | None = None # Legacy support

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

class AuthRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    full_name: str
    phone: str
    school_id: str
    other_school: str | None = None
    board: str
    subjects: list[str]
    username: str
    password: str

# --- JWT Auth Middleware ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = get_student_by_username(username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not authorized. Admin access required.")
    return current_user

# --- Authentication Endpoints ---

@app.post("/api/auth/register")
async def register_student(request: RegisterRequest):
    # Check if username exists
    existing = get_student_by_username(request.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
        
    # Create student dictionary matching Supabase schema
    student_data = {
        "username": request.username.lower().strip(),
        "password_hash": get_password_hash(request.password),
        "full_name": request.full_name,
        "phone": request.phone,
        "school_id": request.school_id,
        "other_school": request.other_school if request.school_id == 'other' else None,
        "board": request.board,
        "subjects": request.subjects,
        "approved": False,
        "is_admin": False
    }
    
    result = create_student(student_data)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create account")
        
    return {
        "uuid": result.get("uuid"), 
        "username": result.get("username"),
        "message": "Registration pending approval"
    }

@app.post("/api/auth/login")
async def login_for_access_token(request: AuthRequest):
    user = get_student_by_username(request.username.lower().strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    if not user.get('approved') and not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Your account is pending approval by Puneet.")
        
    # Create JWT token
    access_token = create_access_token(data={"sub": user["username"]})
    
    # Generate session UUID
    session_id = str(uuid.uuid4())
    
    # Log the login!
    log_session_action(
        session_id=session_id,
        student_uuid=user['uuid'], 
        school_id=user['school_id'],
        action="LOGIN"
    )
    
    # Send safe data down to frontend
    safe_user = {
        "name": user["full_name"],
        "username": user["username"],
        "school_id": user["school_id"],
        "other_school": user["other_school"],
        "subjects": user["subjects"],
        "board": user["board"],
        "uuid": user["uuid"],
        "isAdmin": user.get("is_admin", False)
    }
    
    return {
        "token": access_token,
        "student": safe_user,
        "session_id": session_id
    }

# --- Admin Endpoints ---
@app.post("/api/admin/approve/{username}")
async def approve_student(username: str, admin: dict = Depends(get_current_admin)):
    result = approve_student_in_db(username)
    if not result:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": f"Student {username} approved"}

@app.get("/api/admin/dashboard")
async def admin_dashboard(admin: dict = Depends(get_current_admin)):
    data = get_admin_dashboard_data()
    return data

# --- Chat & AI Endpoints ---

@app.post("/api/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    async def generate():
        try:
            # history context: format for gemini client
            history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]
            current_message = request.messages[-1].content
            
            system_prompt = get_system_prompt(request.subject, request.exam_board, request.level)
            
            # Log the question immediately
            if request.session_id:
                log_session_action(
                    session_id=request.session_id,
                    student_uuid=current_user['uuid'],
                    school_id=current_user['school_id'],
                    action="QUESTION",
                    subject=request.subject,
                    question_preview=current_message[:150]
                )
                
            latest_image = request.messages[-1].image
            stream = get_tutor_response_stream(
                current_message, history, system_prompt, 
                request.subject, request.exam_board, request.level, 
                latest_image
            )
            
            full_response = ""
            for chunk in stream:
                full_response += chunk
                # Still outputting proper JSON formats within the SSE context for the frontend
                yield f"data: {json.dumps({'text': chunk})}\n\n"
                
            # Log completion size
            if request.session_id:
                log_session_action(
                    session_id=request.session_id,
                    student_uuid=current_user['uuid'],
                    school_id=current_user['school_id'],
                    action="RESPONSE",
                    subject=request.subject,
                    response_length=len(full_response)
                )
                
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/generate")
async def generate_questions(request: GenerateRequest, current_user: dict = Depends(get_current_user)):
    try:
        qs = generate_practice_questions(
            request.subject, request.topic, request.exam_board, request.level, request.num_questions
        )
        return qs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mark")
async def mark_answer(request: MarkRequest, current_user: dict = Depends(get_current_user)):
    try:
        result = mark_student_answer(
            request.question, request.mark_scheme, request.student_answer, request.subject, request.exam_board
        )
        
        save_practice_result(
            current_user['uuid'], request.subject, request.topic, request.exam_board, request.level,
            request.question, "", request.student_answer, result.marks_awarded, result.marks_available,
            result.feedback
        )
            
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress")
async def get_progress(current_user: dict = Depends(get_current_user)):
    history = get_practice_history(current_user['uuid'])
    return {"history": history}

# Serve the widget
@app.get("/widget/widget.js")
async def serve_widget():
    # Construct path dynamically relative to the backend cwd assuming a parallel widget dir
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
