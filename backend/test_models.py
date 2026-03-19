import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
try:
    models = list(client.models.list())
    for model in models:
        caching = "createCachedContent" in getattr(model, "supported_generation_methods", [])
        if "3" in model.name or "flash" in model.name:
            print(f"{model.name} - Caching: {caching}")
except Exception as e:
    print(f"Error: {e}")
