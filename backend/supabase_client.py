from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------
# Fail-fast config
# ----------------------------------------------------------------------
def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"{name} is required but missing from environment variables.")
    return v

SUPABASE_URL = _require("SUPABASE_URL")

# Accept either SUPABASE_SERVICE_KEY or SUPABASE_KEY (service role)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY or SUPABASE_KEY is required but missing from environment variables.")

_sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_supabase() -> Client:
    """Initialize and return a Supabase client using the service_role key to bypass RLS."""
    return _sb

def verify_supabase_jwt(jwt_token: str):
    """Verify a Supabase Auth JWT token and return the user object."""
    try:
        supabase = get_supabase()
        response = supabase.auth.get_user(jwt_token)
        if response and response.user:
            return response.user
        return None
    except Exception as e:
        print(f"Error verifying Supabase JWT: {e}")
        return None

def get_student_by_id(student_id: str):
    """Fetch student profile by ID."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').select('*').eq('id', student_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting student: {e}")
        return None

def create_student(student_data: dict):
    """Create a new student record (managed by staff)."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').insert(student_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating student: {e}")
        return None

def get_students_list():
    """Fetch all students for staff dashboards."""
    try:
        supabase = get_supabase()
        response = supabase.table('students').select('*').order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting students list: {e}")
        return []

def save_consent(consent_data: dict):
    """Save or update parental consent status. Implements upsert."""
    try:
        supabase = get_supabase()
        response = supabase.table('consents').upsert(
            consent_data, 
            on_conflict='student_id,purpose'
        ).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error saving consent: {e}")
        return None

def get_consents_for_student(student_id: str):
    """Fetch all consent records for a specific student."""
    try:
        supabase = get_supabase()
        response = supabase.table('consents').select('*').eq('student_id', student_id).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting consents: {e}")
        return []

def get_consent_events(student_id: str):
    """Fetch the append-only audit trail for a student."""
    try:
        supabase = get_supabase()
        response = supabase.table('consent_events').select('*').eq('student_id', student_id).order('event_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting consent events: {e}")
        return []

def create_session(student_id: str, model: str):
    """Create a new chat session."""
    try:
        supabase = get_supabase()
        response = supabase.table('sessions').insert({
            'student_id': student_id,
            'model': model
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating session: {e}")
        return None

def get_admin_dashboard_data():
    """Fetch stats and data for the staff admin dashboard."""
    try:
        supabase = get_supabase()
        students = supabase.table('students').select('*').execute()
        interactions = supabase.table('interactions').select('id, student_id, created_at, subject, topic, cost_usd').order('created_at', desc=True).limit(100).execute()
        spend = supabase.table('monthly_spend_usd').select('*').execute()
        
        return {
            "students": students.data if students.data else [],
            "recent_interactions": interactions.data if interactions.data else [],
            "monthly_spend": spend.data if spend.data else []
        }
    except Exception as e:
        print(f"Error getting admin dashboard data: {e}")
        return {"students": [], "recent_interactions": [], "monthly_spend": []}

def get_student_interactions(student_id: str):
    """Fetch all interactions for a specific student to show progress history."""
    try:
        supabase = get_supabase()
        response = supabase.table('interactions').select('id, created_at, subject, topic, difficulty, resolved').eq('student_id', student_id).order('created_at', desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error getting student interactions: {e}")
        return []
