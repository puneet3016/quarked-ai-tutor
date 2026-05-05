"""Upload the poster image to Meta WhatsApp media servers and return the media_id."""
import requests
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

TOKEN = os.environ.get('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID')
POSTER_PATH = "/Users/puneetsharma/Desktop/quarked-poster (3).jpg"

print(f"Uploading: {POSTER_PATH}")
print(f"File exists: {os.path.exists(POSTER_PATH)}")

with open(POSTER_PATH, 'rb') as f:
    response = requests.post(
        f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media",
        headers={"Authorization": f"Bearer {TOKEN}"},
        data={"messaging_product": "whatsapp"},
        files={"file": ("quarked-poster.jpg", f, "image/jpeg")}
    )

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
