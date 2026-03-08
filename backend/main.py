from fastapi import FastAPI, HTTPException, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json
import os
from dotenv import load_dotenv

from prompts import get_system_prompt
from gemini_client import get_tutor_response_stream, generate_practice_questions, mark_student_answer, initialize_caches
from supabase_client import log_conversation, save_practice_result, get_practice_history, get_student_profile_by_token

load_dotenv()

app = FastAPI(title="Quarked AI Tutor Backend")

@app.on_event("startup")
async def startup():
    initialize_caches()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://quarked.tech", "http://localhost:8000"],
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

class AuthRequest(BaseModel):
    username: str
    password: str

# --- Middleware/Auth (Optional simple check) ---
async def get_current_user(request: Request):
    # Retrieve auth header. This is stubbed for widget simple integration
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        profile = get_student_profile_by_token(token)
        if profile:
            return profile['id']
    return None

# --- Endpoints ---
@app.post("/api/chat")
async def chat(request: ChatRequest):
    async def generate():
        try:
            # history context: format for gemini client
            history = [{"role": m.role, "content": m.content} for m in request.messages[:-1]]
            current_message = request.messages[-1].content
            
            system_prompt = get_system_prompt(request.subject, request.exam_board, request.level)
            
            # log entire messages up to current
            if request.student_id:
                # Async background logging would be better suited here
                log_conversation(
                    request.student_id, 
                    request.subject, 
                    request.exam_board, 
                    request.level, 
                    history + [{"role": "user", "content": current_message}]
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
                yield f"data: {json.dumps({'text': chunk})}\n\n"
                
            if request.student_id:
                log_conversation(
                    request.student_id, 
                    request.subject, 
                    request.exam_board, 
                    request.level, 
                    history + [
                        {"role": "user", "content": current_message},
                        {"role": "assistant", "content": full_response}
                    ]
                )
                
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/generate")
async def generate_questions(request: GenerateRequest):
    try:
        qs = generate_practice_questions(
            request.subject, request.topic, request.exam_board, request.level, request.num_questions
        )
        return qs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mark")
async def mark_answer(request: MarkRequest):
    try:
        result = mark_student_answer(
            request.question, request.mark_scheme, request.student_answer, request.subject, request.exam_board
        )
        
        if request.student_id:
            save_practice_result(
                request.student_id, request.subject, request.topic, request.exam_board, request.level,
                request.question, "", request.student_answer, result.marks_awarded, result.marks_available,
                result.feedback
            )
            
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/progress/{student_id}")
async def get_progress(student_id: str):
    history = get_practice_history(student_id)
    return {"history": history}

# Stub auth endpoints based on prompt specs
@app.post("/api/auth/login")
async def login(request: AuthRequest):
    # Replace with real verification logic using Supabase Auth
    # Returning a mock token for MVP simplicity
    return {"token": "mock_jwt_token", "student_id": "optional-id"}

@app.post("/api/auth/register")
async def register(request: AuthRequest):
    return {"status": "ok", "message": "Registered"}

@app.get("/api/models")
async def list_models():
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        model_list = [m.name for m in client.models.list()]
        return {"models": model_list}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/models/caching")
async def check_caching():
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        cache_support = {}
        for m in client.models.list():
            if '3' in getattr(m, 'name', '') or 'flash' in getattr(m, 'name', ''):
                cache_support[m.name] = 'createCachedContent' in getattr(m, 'supported_generation_methods', [])
        return {"caching_models": cache_support}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/models/v1alpha")
async def check_v1alpha():
    try:
        from google import genai
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'), http_options={'api_version': 'v1alpha'})
        model_list = [m.name for m in client.models.list()]
        return {"v1alpha_models": model_list}
    except Exception as e:
        return {"error": str(e)}

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
