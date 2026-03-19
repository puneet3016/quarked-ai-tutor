import os
from dotenv import load_dotenv
from google import genai
load_dotenv()
try:
    client = genai.Client()
    for model in client.models.list():
        if "createCachedContent" in getattr(model, "supported_generation_methods", []):
            print(f"Supported model: {model.name}")
except Exception as e:
    print(f"Error: {e}")
