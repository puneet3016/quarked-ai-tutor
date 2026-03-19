import os
from dotenv import load_dotenv
from google import genai
load_dotenv()
try:
    client = genai.Client()
    for model in client.models.list():
        supports_caching = "createCachedContent" in getattr(model, "supported_generation_methods", []) or 'cachedContent' in model.name
        if "createCachedContent" in getattr(model, "supported_generation_methods", []):
            print(f"Supported model: {model.name}")
except Exception as e:
    print(f"Error: {e}")
