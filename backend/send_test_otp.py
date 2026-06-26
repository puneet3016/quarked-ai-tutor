import requests
import json

def main():
    print("==================================================")
    print("       Send Test Parental Consent OTP Script      ")
    print("==================================================")
    
    parent_email = input("Enter email address to send OTP to: ").strip()
    if not parent_email:
        print("Error: Email is required.")
        return

    url = "https://quarked-ai-tutor-production.up.railway.app/consent/otp"
    payload = {
        "destination": parent_email,
        "channel": "email"
    }

    print(f"\nSending POST request to {url}...")
    try:
        r = requests.post(url, json=payload)
        print(f"Status Code: {r.status_code}")
        print("Response:", r.text)
        if r.status_code == 200:
            challenge_id = r.json().get("challenge_id")
            print(f"\nSuccess! OTP sent to '{parent_email}'.")
            print(f"Challenge ID: {challenge_id}")
            print("Please check your email inbox (and spam folder) for the 6-digit code.")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()
