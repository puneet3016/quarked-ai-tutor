import base64
from main import app
from pydantic import BaseModel
from fastapi.testclient import TestClient

client = TestClient(app)

# minimal transparent 1x1 png base64
dummy_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

payload = {
    "messages": [
        {"role": "user", "content": "What is in this image?", "image": dummy_img}
    ],
    "subject": "Physics",
    "exam_board": "IGCSE",
    "level": "Extended"
}

response = client.post("/api/chat", json=payload)
print(response.status_code)
for chunk in response.iter_lines():
    print(chunk)
