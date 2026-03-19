import os
from dotenv import load_dotenv
load_dotenv()
from google import genai
client = genai.Client(http_options={'api_version': 'v1alpha'})
try:
    response = client.models.generate_content(
        model='gemini-3.0-flash',
        contents='Hello'
    )
    print("Success:", response.text)
except Exception as e:
    print("Error:", e)
