"""
Test script - sends ONE message to YOUR OWN number first.
Replace TEST_NUMBER with your own WhatsApp number to verify it works.
"""
import requests
import os
from dotenv import load_dotenv

# Load from .env file in same directory
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID')

# !! CHANGE THIS to your own WhatsApp number (with country code, no + or spaces)
TEST_NUMBER = "919460459269"  # Puneet's MAIN number (test message goes here)

def send_test():
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": TEST_NUMBER,
        "type": "template",
        "template": {
            "name": "quarked_premium_mentoring",
            "language": {"code": "en"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"id": "1242555464702068"}
                        }
                    ]
                }
            ]
        }
    }
    
    print(f"Sending test message to {TEST_NUMBER}...")
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    send_test()
