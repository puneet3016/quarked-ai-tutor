import os
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Literal

client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
MODEL = 'gemini-1.5-flash-002'

import base64
import re

def strip_images_from_text(text: str) -> str:
    """Removes HTML img tags with base64 data from text so it doesn't blow up the prompt."""
    if not text: return text
    return re.sub(r'(?:<br>)?<img src="[^"]+"[^>]*>', '[Image attached]', text)

# CACHES dictionary to hold the references to cached contents
CACHES = {}

def create_subject_cache(subject: str, exam_board: str, level: str, system_prompt: str):
    cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name=f"quarked-{subject}-{exam_board}-{level}",
            system_instruction=system_prompt,
            ttl="86400s",  # 24 hours — renew daily
        )
    )
    return cache

def get_or_create_cache(subject: str, exam_board: str, level: str, system_prompt: str):
    key = f"{subject}-{exam_board}-{level}"
    if key not in CACHES:
        CACHES[key] = create_subject_cache(subject, exam_board, level, system_prompt)
    return CACHES[key]

def get_tutor_response_stream(user_message: str, conversation_history: list, system_prompt: str, subject: str, exam_board: str, level: str, latest_image: str = None):
    """Stream a tutoring response for real-time display."""
    cache = get_or_create_cache(subject, exam_board, level, system_prompt)
    
    contents = []
    for msg in conversation_history:
        role = 'user' if msg['role'] == 'user' else 'model'
        clean_text = strip_images_from_text(msg['content'])
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=clean_text)]))
        
    user_parts = [types.Part.from_text(text=strip_images_from_text(user_message))]
    
    if latest_image:
        try:
            # Handle data:image/jpeg;base64,... format
            if ',' in latest_image:
                mime_type = latest_image.split(';')[0].split(':')[1]
                base64_data = latest_image.split(',')[1]
            else:
                mime_type = 'image/jpeg' # fallback
                base64_data = latest_image
                
            image_bytes = base64.b64decode(base64_data)
            user_parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )
        except Exception as e:
            print(f"Error decoding image: {e}")

    contents.append(types.Content(role='user', parts=user_parts))

    response = client.models.generate_content_stream(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            cached_content=cache.name,
            temperature=0.3,
            max_output_tokens=2000,
        ),
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text

# Structured output for question generation
class GeneratedQuestion(BaseModel):
    question_text: str = Field(description="The question exactly as it would appear on an exam paper")
    command_term: str = Field(description="The command term used e.g. Calculate, Explain, Evaluate")
    total_marks: int = Field(description="Total marks allocated")
    mark_scheme: List[str] = Field(description="Mark scheme points, one per mark")
    model_answer: str = Field(description="Complete model answer that would earn full marks")
    topic: str = Field(description="The specific topic/subtopic")
    difficulty: Literal["Core", "Extended", "SL", "HL"]

class QuestionSet(BaseModel):
    questions: List[GeneratedQuestion]

def generate_practice_questions(subject: str, topic: str, exam_board: str,
                                 level: str, num_questions: int = 3) -> QuestionSet:
    prompt = f"""Generate {num_questions} authentic {exam_board} {level} {subject} exam questions on: {topic}.

For each question:
- Use appropriate command terms for the mark allocation
- 1-2 mark: State, Define, Identify, Calculate (single-step)
- 3-4 mark: Describe, Explain, Calculate (multi-step)
- 5-6 mark: Explain, Compare, Analyse
- 7-8+ mark: Evaluate, Discuss, To what extent

Mark scheme conventions:
- M marks for method, A marks for accuracy, B marks for independent correct answers
- Include ECF (Error Carried Forward) where appropriate
- Calculations: formula (M1) → substitution (M1) → answer with units (A1)
- Explanations: each distinct valid point = 1 mark

Mix different mark values. Include at least one calculation and one explanation."""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={'response_mime_type': 'application/json', 'response_schema': QuestionSet},
    )
    return QuestionSet.model_validate_json(response.text)

class MarkResult(BaseModel):
    marks_awarded: int
    marks_available: int
    mark_breakdown: List[str]
    feedback: str
    model_answer: str

def mark_student_answer(question: str, mark_scheme: List[str], student_answer: str,
                         subject: str, exam_board: str) -> MarkResult:
    prompt = f"""You are a senior {exam_board} {subject} examiner. Mark this answer.

QUESTION: {question}
MARK SCHEME ({len(mark_scheme)} marks):
{chr(10).join(f'- {ms}' for ms in mark_scheme)}
STUDENT'S ANSWER: {student_answer}

Rules:
- Positive marking only — never deduct marks
- ECF/FT: if wrong value carried forward but correct method, award method marks
- For calculations: check formula → substitution → answer with units
- "cao" = correct answer only, "isw" = ignore subsequent working
- Be encouraging but honest"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={'response_mime_type': 'application/json', 'response_schema': MarkResult},
    )
    return MarkResult.model_validate_json(response.text)
