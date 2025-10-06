import os
import asyncio
import json
import base64
import websockets
from flask import Flask, request, Response
from flask_sock import Sock
from dotenv import load_dotenv
from twilio.rest import Client

# ---------------------------------------------------------------------
# 🔧 Config
# ---------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://twilio-realtime-agent-1.onrender.com")

app = Flask(__name__)
sock = Sock(app)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------------------
# 🌐 Make Outbound Call
# ---------------------------------------------------------------------
@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    if not to:
        return {"error": "Missing 'to' param"}, 400

    response = f"""
    <Response>
        <Connect>
            <Stream url="{PUBLIC_URL.replace('https','wss')}/twilio-stream" />
        </Connect>
    </Response>
    """
    call = client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        twiml=response
    )
    print(f"📞 Outbound realtime call started: {to}")
    return {"sid": call.sid}, 200


# ---------------------------------------------------------------------
# 🎧 Twilio Realtime Stream <-> OpenAI Realtime
# ---------------------------------------------------------------------
@sock.route("/twilio-stream")
def twilio_stream(ws):
    print("🎧 Twilio connected, starting Realtime stream...")

    async def handle_audio():
        uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
        headers = [
            ("Authorization", f"Bearer {OPENAI_API_KEY}"),
            ("OpenAI-Beta", "realtime=v1")
        ]

        async with websockets.connect(uri, extra_headers=headers) as openai_ws:
            print("🧠 Connected to OpenAI Realtime API")

            async def from_twilio_to_openai():
                while True:
                    msg = ws.receive()
                    if not msg:
                        break
                    await openai_ws.send(msg)

            async def from_openai_to_twilio():
                async for msg in openai_ws:
                    ws.send(msg)

            await asyncio.gather(from_twilio_to_openai(), from_openai_to_twilio())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(handle_audio())
    except Exception as e:
        print("❌ Error during realtime streaming:", e)
    finally:
        loop.close()
        print("❎ Stream closed")


# ---------------------------------------------------------------------
# ✅ Health check
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return Response("Twilio Realtime Agent is running.", mimetype="text/plain")


# ---------------------------------------------------------------------
# 🚀 Run server
# ---------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 Running on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)