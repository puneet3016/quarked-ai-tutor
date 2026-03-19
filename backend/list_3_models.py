import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client()
models = list(client.models.list())
for m in models:
    name = getattr(m, 'name', '')
    methods = getattr(m, 'supported_generation_methods', [])
    if "3" in name or "flash" in name:
        print(f"Model: {name} | Caching: {'createCachedContent' in methods}")
