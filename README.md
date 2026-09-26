# Jai Kisaan AI - Phase 1

## What works in this build
- Mobile-number based farmer registration (pilot identity, no OTP yet)
- Supabase-backed farmer, field, crop-cycle, farm-event and chat history
- Same field can start a new crop only after current crop is marked harvested
- Crop age auto calculation
- Open-Meteo weather via location name
- Gemini AI chat with actual crop/field/event context
- Gemini image analysis (photo optional)
- AI crop plan generated dynamically; no fixed Day-45 hardcoded spray schedule
- Mandi endpoint never returns hardcoded prices. It shows unavailable until official API is configured.

## Setup
1. Create a Supabase project and run `schema.sql` in SQL Editor.
2. Copy `.env.example` to `.env` and fill Supabase + Gemini values.
3. Configure `DATA_GOV_API_URL` for the official mandi dataset. Optional `DATA_GOV_API_KEY` if required.
4. Install: `pip install -r requirements.txt`
5. Run: `python flask_app.py`
6. Serve `index.html` from the same origin in deployment, or open locally while Flask runs on 127.0.0.1:8000.

## Important
Treatment/brand/dose output is AI guidance, not a guaranteed prescription. The prompt explicitly asks Gemini not to invent uncertain treatment and to request label/local-expert verification.
