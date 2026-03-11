from supabase import create_client, Client
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_supabase() -> Client:
    """Initialize and return a Supabase client."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("WARNING: Supabase URL or Key not found in environment")
    return create_client(url, key)

def get_student_by_username(username: str):
    """Fetch a user by username to verify during login."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').select('*').eq('username', username).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting student: {e}")
        return None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_student(student_data: dict):
    """Insert a new pending student registration."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').insert(student_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating student: {e}")
        return None

def approve_student_in_db(username: str):
    """Admin function to approve a student."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').update({'approved': True}).eq('username', username).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error approving student: {e}")
        return None

def log_session_action(session_id: str, student_uuid: str, school_id: str, action: str, subject: str = None, question_preview: str = None, response_length: int = None):
    """Tracks every login, logout, and question asked."""
    try:
        supabase = get_supabase()
        data = {
            'session_id': session_id,
            'student_uuid': student_uuid,
            'school_id': school_id,
            'action': action,
        }
        if subject: data['subject'] = subject
        if question_preview: data['question_preview'] = question_preview
        if response_length: data['response_length'] = response_length
        supabase.table('sessions').insert(data).execute()
    except Exception as e:
        print(f"Error logging session action {action}: {e}")

def get_admin_dashboard_data():
    """Fetches overview metrics for the admin dashboard."""
    try:
        supabase = get_supabase()
        sessions = supabase.table('sessions').select('*').order('created_at', desc=True).limit(200).execute()
        students = supabase.table('students').select('username, full_name, school_id, other_school, board, subjects, uuid, approved, is_admin').execute()
        return {
            "sessions": sessions.data,
            "students": [s for s in students.data if s.get('is_admin') != True],
            "pending": [s for s in students.data if s.get('approved') == False and s.get('is_admin') != True]
        }
    except Exception as e:
        print(f"Error getting admin data: {e}")
        return {"sessions": [], "students": [], "pending": []}

def log_conversation(student_id: str, subject: str, exam_board: str, level: str, messages: list, source: str = 'web'):
    """Log conversation messages to Supabase."""
    try:
        supabase = get_supabase()
        supabase.table('conversations').insert({
            'student_id': student_id,
            'subject': subject,
            'exam_board': exam_board,
            'level': level,
            'messages': messages,
            'source': source
        }).execute()
    except Exception as e:
        print(f"Error logging conversation: {e}")

def get_student_profile_by_token(token: str):
    """Old stub profile fetched by stub auth token."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').select('*').eq('auth_token', token).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting profile: {e}")
        return None

def save_practice_result(student_id: str, subject: str, topic: str, exam_board: str, level: str, 
                         question: str, command_term: str, student_answer: str, 
                         marks_awarded: int, marks_available: int, feedback: str):
    """Save practice marking results."""
    try:
        supabase = get_supabase()
        supabase.table('practice_results').insert({
            'student_id': student_id,
            'subject': subject,
            'topic': topic,
            'exam_board': exam_board,
            'level': level,
            'question_text': question,
            'command_term': command_term,
            'student_answer': student_answer,
            'marks_awarded': marks_awarded,
            'marks_available': marks_available,
            'feedback': feedback
        }).execute()
    except Exception as e:
        print(f"Error saving practice result: {e}")

def get_practice_history(student_id: str):
    """Retrieve practice history for a user."""
    try:
        supabase = get_supabase()
        response = supabase.table('practice_results').select('*').eq('student_id', student_id).order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error retrieving practice history: {e}")
        return []
