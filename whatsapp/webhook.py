from flask import Flask, request, jsonify
import requests, os
from google import genai
from google.genai import types

app = Flask(__name__)
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
MODEL = 'gemini-3.0-flash'

WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')

conversations = {}  # In production, use Redis or Supabase

WA_SYSTEM_PROMPT = """You are the Quarked AI Tutor on WhatsApp, built by Puneet Sharmma.

WHATSAPP RULES:
- Keep responses under 300 words
- Plain text only (no markdown, no LaTeX)
- Use Unicode math: ², ³, ×, ÷, →, ≤, ≥, ≠, π, √
- Numbered steps for procedures
- Emojis sparingly: ✅ ❌ 💡 📝 🎯

SHORTCUTS:
- Student sends topic name → generate a quick practice question
- "hint" → hint for last question
- "answer" → full solution
- "more" → another similar question
- "score" → recent practice stats
- "physics" / "maths" / "chem" / "econ" / "cs" → switch subject

TEACHING: Use Socratic method. Guide, don't just answer. Be encouraging."""

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get('hub.verify_token') == VERIFY_TOKEN:
        return request.args.get('hub.challenge'), 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def handle():
    body = request.get_json()
    if body and body.get('entry'):
        for entry in body['entry']:
            for change in entry.get('changes', []):
                value = change.get('value', {})
                if 'messages' in value:
                    msg = value['messages'][0]
                    if msg['type'] == 'text':
                        reply = get_response(msg['from'], msg['text']['body'])
                        send_message(msg['from'], reply)
                    elif msg['type'] == 'image':
                        caption = msg['image'].get('caption', 'Please explain this image.')
                        media_id = msg['image']['id']
                        image_bytes, mime_type = download_whatsapp_media(media_id)
                        if image_bytes:
                            reply = get_response(msg['from'], caption, image_bytes, mime_type)
                        else:
                            reply = "Sorry, I couldn't download the image right now."
                        send_message(msg['from'], reply)
    return jsonify({"status": "ok"}), 200

def download_whatsapp_media(media_id):
    """Download media from WhatsApp Cloud API."""
    url_response = requests.get(
        f"https://graph.facebook.com/v21.0/{media_id}",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    )
    if url_response.status_code != 200:
        return None, None
    
    media_url = url_response.json().get('url')
    mime_type = url_response.json().get('mime_type')
    
    media_response = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    )
    if media_response.status_code == 200:
        return media_response.content, mime_type
    return None, None

def get_response(user_id, message, image_bytes=None, mime_type=None):
    if user_id not in conversations:
        conversations[user_id] = []
    conversations[user_id].append({'role': 'user', 'content': message})
    recent = conversations[user_id][-20:]
    
    contents = []
    for m in recent[:-1]:
        role = 'user' if m['role'] == 'user' else 'model'
        contents.append(types.Content(role=role, parts=[types.Part(text=m['content'])]))
        
    current_parts = []
    if image_bytes and mime_type:
        current_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    current_parts.append(types.Part(text=message))
    contents.append(types.Content(role='user', parts=current_parts))
        
    try:
        response = client.models.generate_content(
            model=MODEL, 
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=WA_SYSTEM_PROMPT,
                temperature=0.3, 
                max_output_tokens=800
            )
        )
        reply = response.text
        conversations[user_id].append({'role': 'assistant', 'content': reply})
        return reply
    except Exception as e:
        print(f"Error communicating with AI: {e}")
        return "I'm having trouble thinking right now. Please try again in a minute."

def send_message(to, text):
    try:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            requests.post(
                f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": chunk}}
            )
    except Exception as e:
        print(f"Failed to send WA message: {e}")

if __name__ == '__main__':
    app.run(port=5000)
