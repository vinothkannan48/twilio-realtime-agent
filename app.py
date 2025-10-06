import os, html
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# --- Config ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER  = os.getenv("TWILIO_FROM_NUMBER")
OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
PUBLIC_URL          = os.getenv("PUBLIC_URL", "").rstrip("/")
HOST = "0.0.0.0"
PORT = 5050

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, OPENAI_API_KEY, PUBLIC_URL]):
    print("⚠️ Missing environment vars, check .env")

# --- Clients ---
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)
conversations = {}

SYSTEM_PROMPT = """You are a friendly Tamil-English bilingual assistant.
Detect whether the user speaks Tamil or English and reply in the same language.
Start every call by greeting Vinod personally.
Keep responses short and natural for voice.
If user says bye or thank you, end the conversation politely.
"""

def gpt_reply(call_sid, text):
    history = conversations.get(call_sid, [])
    history.append({"role": "user", "content": text})

    try:
        r = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            max_tokens=200,
            temperature=0.6,
        )
        reply = r.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        reply = "Sorry, I'm having trouble understanding now."

    history.append({"role": "assistant", "content": reply})
    conversations[call_sid] = history
    return reply


@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    call = twilio_client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        url=f"{PUBLIC_URL}/voice",
        method="POST"
    )
    print(f"📞 Call started to {to}")
    return {"sid": call.sid}


@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{PUBLIC_URL}/gather",
        method="POST",
        speechTimeout="auto",
        language="en-IN"  # ✅ supported by Twilio
    )

    # Friendly greeting
    gather.say("Hi Vinod! How are you? Is it the right time to talk?",
               voice="alice", language="en-IN")

    resp.append(gather)
    resp.say("Okay, bye!", voice="alice", language="en-IN")
    resp.hangup()
    return Response(str(resp), mimetype="text/xml")


@app.route("/gather", methods=["POST"])
def gather():
    call_sid = request.form.get("CallSid")
    speech_result = html.unescape(request.form.get("SpeechResult", "")).strip()
    print(f"/gather SpeechResult={speech_result}")

    if not speech_result:
        # Reprompt if nothing heard
        resp = VoiceResponse()
        g = Gather(
            input="speech",
            action=f"{PUBLIC_URL}/gather",
            method="POST",
            speechTimeout="auto",
            language="en-IN"
        )
        g.say("Sorry, I didn’t catch that. Please repeat.", voice="alice", language="en-IN")
        resp.append(g)
        return Response(str(resp), mimetype="text/xml")

    # --- Generate AI reply ---
    reply = gpt_reply(call_sid, speech_result)
    print(f"AI reply: {reply}")

    lang = "en-IN"
    if any("\u0b80" <= c <= "\u0bff" for c in reply):
        reply = "Tamil detected. " + reply  # Twilio can't TTS Tamil yet
        lang = "en-IN"

    # --- End-of-conversation detection ---
    user_lower = speech_result.lower()
    reply_lower = reply.lower()
    end_words = ["bye", "goodbye", "thank", "see you", "talk later", "see you later"]

    should_end = any(w in user_lower for w in end_words) or any(w in reply_lower for w in end_words)

    # --- Build TwiML ---
    resp = VoiceResponse()
    resp.say(reply, voice="alice", language=lang)

    if should_end:
        resp.say("Okay Vinod, take care! Goodbye.", voice="alice", language=lang)
        resp.hangup()
        print("🔚 Ending call now.")
    else:
        g = Gather(
            input="speech",
            action=f"{PUBLIC_URL}/gather",
            method="POST",
            speechTimeout="auto",
            language="en-IN"
        )
        resp.append(g)

    return Response(str(resp), mimetype="text/xml")


if __name__ == "__main__":
    print(f"🚀 Running on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)