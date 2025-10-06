import os
import json
from flask import Flask, request, Response
from flask_sock import Sock
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# --- Environment ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL")

# --- Setup Flask + WebSocket ---
app = Flask(__name__)
sock = Sock(app)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Basic check route ---
@app.route("/", methods=["GET"])
def home():
    return "✅ Flask Realtime Agent Running", 200

# --- TwiML endpoint for Twilio call ---
@app.route("/media-stream", methods=["POST"])
def media_stream():
    twiml = f"""
    <Response>
        <Connect>
            <Stream url="wss://twilio-realtime-agent.onrender.com/twilio-stream" />
        </Connect>
    </Response>
    """
    return Response(twiml.strip(), mimetype="text/xml")

# --- WebSocket endpoint Twilio connects to ---
@sock.route("/twilio-stream")
def twilio_stream(ws):
    print("🔗 Twilio media stream connected")
    try:
        while True:
            message = ws.receive()
            if message is None:
                print("❌ Twilio disconnected")
                break

            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"🎧 Stream started: {stream_sid}")

            elif event == "media":
                # Audio packets are base64 encoded, you could forward them to OpenAI Realtime later
                pass

            elif event == "stop":
                print("🛑 Stream stopped")
                break
    except Exception as e:
        print("⚠️ WebSocket error:", e)

# --- Outbound call trigger ---
@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    if not to:
        return {"error": "Missing 'to' parameter"}, 400

    call = twilio_client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        url=f"{PUBLIC_URL}/media-stream",
        method="POST"
    )
    print(f"📞 Outbound realtime call started to {to}, SID: {call.sid}")
    return {"sid": call.sid}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))