import os
import requests
from dotenv import load_dotenv
import urllib3

urllib3.disable_warnings()

load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
if not api_key:
    print("NO API KEY FOUND")
    exit(1)
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url, verify=False)
    data = response.json()
    working_models = []
    for m in data.get('models', []):
        if 'generateContent' in m.get('supportedGenerationMethods', []):
            print(f"Supported: {m['name']}")
except Exception as e:
    print(f"Error: {e}")
