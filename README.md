# OpenAI + Twilio Outbound Voice Appointment Bot (Python)

## What this does
- Places outbound calls via Twilio.
- Uses Twilio's speech recognition to capture user speech.
- Sends transcribed text to OpenAI (GPT-5) to behave as an appointment booking assistant.
- Replies in the same language (English / Tamil detection supported).
- Ends the call after booking confirmation.

## Setup (local)
1. Install Python 3.9+.
2. Unzip the project and `cd` into it.
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Copy `.env.example` to `.env` and fill in your keys. Make sure `PUBLIC_URL` is a public URL reachable by Twilio (use ngrok for testing).
6. Run the Flask app:
   ```bash
   flask run --host=0.0.0.0 --port=5000
   ```
   or
   ```bash
   python app.py
   ```
7. Expose your local server (if testing) using ngrok:
   ```bash
   ngrok http 5000
   ```
   Set `PUBLIC_URL` in `.env` to the ngrok URL (e.g. https://abcd.ngrok.io)
8. Trigger an outbound call (example):
   ```bash
   curl -X POST -d "to=+91xxxxxxxxxx" http://localhost:5000/make_call
   ```

## Notes & Next steps
- This project uses an in-memory conversation store (dictionary). For production, use a persistent DB (Redis/Postgres).
- The assistant is instructed to include the token `[BOOKING_COMPLETE]` when it has all info; adjust the system prompt to fit your booking flow.
- If you need richer TTS or STT (better Tamil support), consider integrating OpenAI's audio endpoints or a speech provider.
- Add logging, retries, and error handling for robustness.