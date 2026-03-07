from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

def get_supabase() -> Client:
    """Initialize and return a Supabase client."""
    return create_client(
        os.environ.get("SUPABASE_URL", ""),
        os.environ.get("SUPABASE_KEY", "")
    )

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
    """Get a student profile from Supabase by auth_token."""
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
