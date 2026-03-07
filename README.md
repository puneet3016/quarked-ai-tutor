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
3. Set environment variables:
   - GEMINI_API_KEY
   - SUPABASE_URL
   - SUPABASE_KEY
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
