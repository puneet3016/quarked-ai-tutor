# Quarked AI Tutor - Backend + Widget + WhatsApp MVP

This repository contains the completely integrated backend systems mapping the Google Gemini API to the `quarked-2.0` architecture.

## Deployment Instructions

### Step 1: Get API Keys
1. **Gemini**: https://aistudio.google.com/apikey → Create Key (free, instant)
2. **Supabase**: https://supabase.com → New Project → Settings → API → copy URL + anon key
3. **WhatsApp** (optional, do later): https://developers.facebook.com → Create App → WhatsApp product

### Step 2: Deploy Backend to Railway
1. Push code to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Set the following environment variables:
   * **Required Core API Keys & Database Secrets:**
     * `GEMINI_API_KEY`: Google Gemini API key.
     * `SUPABASE_URL`: Your Supabase Project URL (e.g. `https://xxx.supabase.co`).
     * `SUPABASE_SERVICE_KEY`: Your Supabase `service_role` key (required to bypass RLS).
     * `QUESTION_ENC_KEY`: A 32-byte base64 Fernet encryption key for encrypting stored student question texts (generate with `cryptography.fernet.Fernet.generate_key()`).
     * `OTP_PEPPER`: A secure secret string used as a pepper for hashing parental verification OTP codes.
   * **Required for Email Consent OTP Channel:**
     * `RESEND_API_KEY`: Your Resend.com API key.
     * `OTP_FROM_EMAIL`: Your verified sending domain address (e.g., `Quarked <consent@yourdomain.com>`).
   * **Optional Cost & Safety Limits:**
     * `MONTHLY_BUDGET_INR`: The hard spend budget cap in INR per month (default: `5000`).
     * `USD_INR_RATE`: Exchange rate used for conversion (default: `86`).
     * `GST_MULTIPLIER`: GST overhead multiplier (default: `1.18` for 18% India GST).
     * `PER_STUDENT_DAILY_REQUEST_CAP`: Daily chat request limit per student (default: `50`).
     * `MAX_OUTPUT_TOKENS`: Hard output token cap per Gemini call (default: `1024`).
     * `OTP_TTL_SECONDS`: Expiry window for OTP challenges in seconds (default: `600`).
4. Railway gives you a public URL (e.g., quarked-tutor.up.railway.app)

### Step 3: Create Supabase Tables
1. Go to Supabase dashboard → SQL Editor
2. Paste and run the required SQL schemas included in the implementation instructions.

### Step 4: Add Widget to quarked.tech
1. Add the loader script tag to your `index.html` file right before `</body>`:
```html
<!-- Quarked AI Tutor Widget -->
<script src="https://YOUR-RAILWAY-URL.up.railway.app/widget/widget-loader.js"></script>
```

### Step 5: Test Web API locally for debugging
Using pip/uvicorn:
```bash
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
# navigate to localhost:8000/docs for interactive OpenAPI panel
```
