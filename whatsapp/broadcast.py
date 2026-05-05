import pandas as pd
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', 'mock_token')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', 'mock_id')

# Ensure variables are mapped
# if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
#     print("ERROR: Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID in environment.")
#     exit(1)

# Configuration
EXCEL_FILE = "/Users/puneetsharma/Downloads/whatsapp_contacts_227.xlsx"
TEMPLATE_NAME = "quarked_premium_mentoring"
LANGUAGE_CODE = "en"

def send_whatsapp_template(to_number, template_name, language_code):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"id": "1242555464702068"}
                        }
                    ]
                }
            ]
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response

def parse_phone_number(num):
    """Cleans phone numbers extracted from pandas."""
    try:
        # Convert floats like 9.191673e+11 to strings like 919167300000
        clean_num = str(int(float(num)))
        return clean_num
    except Exception:
        return None

def main():
    print(f"Loading contacts from {EXCEL_FILE}...")
    try:
        df = pd.read_excel(EXCEL_FILE)
    except FileNotFoundError:
        print("Excel file not found!")
        return
        
    print(f"Loaded {len(df)} contacts. Preparing to send template: '{TEMPLATE_NAME}'\n")
    
    success_count = 0
    fail_count = 0

    for index, row in df.iterrows():
        raw_number = row.get('Phone Number')
        name = row.get('Name', 'Unknown')
        
        # In this dry run/testing phase, remove the break if you want to blast everyone
        # Currently, just doing a dry run print
        number_str = parse_phone_number(raw_number)
        
        if not number_str:
            print(f"Skipping {name}: Invalid phone number format ({raw_number})")
            fail_count += 1
            continue
            
        print(f"[{index+1}/{len(df)}] Sending to {name} ({number_str})... ", end="")
        
        response = send_whatsapp_template(number_str, TEMPLATE_NAME, LANGUAGE_CODE)
        if response.status_code == 200:
            print("✅ SENT")
            success_count += 1
        else:
            err = response.json().get('error', {}).get('message', 'Unknown error')
            print(f"❌ FAILED: {err}")
            fail_count += 1
        
        import time
        time.sleep(0.5)  # small delay to avoid rate limits

if __name__ == "__main__":
    main()
