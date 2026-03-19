import requests

payload = {
    "messages": [
        {"role": "user", "content": "Hello, this is a test"}
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
