import requests
import json

dummy_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

payload = {
    "messages": [
        {"role": "user", "content": "What is in this image?", "image": dummy_img}
    ],
    "subject": "Physics",
    "exam_board": "IGCSE",
    "level": "Extended"
}

url = "https://quarked-ai-tutor-production.up.railway.app/api/chat"

try:
    with requests.post(url, json=payload, stream=True) as r:
        print(f"Status Code: {r.status_code}")
        for line in r.iter_lines():
            if line:
                print(line.decode('utf-8'))
except Exception as e:
    print(f"Request failed: {e}")
