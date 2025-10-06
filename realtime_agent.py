import os
import asyncio
import json
import websockets
from flask import Flask, request, Response
from flask_sock import Sock
from dotenv import load_dotenv
from twilio.rest import Client

# ---------------------------------------------------------------------
# 🔧 Configuration
# ---------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://twilio-realtime-agent-1.onrender.com")

app = Flask(__name__)
sock = Sock(app)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------------------
# 📞 Outbound call
# ---------------------------------------------------------------------
@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    if not to:
        return {"error": "Missing 'to' param"}, 400

    twiml = f"""
    <Response>
        <Connect>
            <Stream url="{PUBLIC_URL.replace('https','wss')}/twilio-stream" />
        </Connect>
    </Response>
    """
    call = twilio_client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        twiml=twiml
    )
    print(f"📞 Outbound realtime call started: {to}")
    return {"sid": call.sid}, 200


# ---------------------------------------------------------------------
# 🔁 Twilio <-> OpenAI streaming bridge
# ---------------------------------------------------------------------
@sock.route("/twilio-stream")
def twilio_stream(ws):
    print("🎧 Twilio connected, starting stream...")

    async def bridge():
        uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
        headers = [
            ("Authorization", f"Bearer {OPENAI_API_KEY}"),
            ("OpenAI-Beta", "realtime=v1")
        ]

        async with websockets.connect(uri, extra_headers=headers) as ai_ws:
            print("🧠 Connected to OpenAI Realtime API")

            # Send a greeting immediately so OpenAI speaks first
            greeting_event = {
                "type": "response.create",
                "response": {
                    "instructions": "Greet the caller politely in English and Tamil. Ask how you can help them.",
                    "modalities": ["audio"],
                    "conversation": "conversation_1"
                }
            }
            await ai_ws.send(json.dumps(greeting_event))

            async def from_twilio():
                while True:
                    msg = ws.receive()
                    if not msg:
                        break
                    await ai_ws.send(msg)

            async def from_openai():
                async for msg in ai_ws:
                    ws.send(msg)

            await asyncio.gather(from_twilio(), from_openai())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bridge())
    except Exception as e:
        print("❌ Stream error:", e)
    finally:
        loop.close()
        print("❎ Stream closed")


# ---------------------------------------------------------------------
# 🩺 Health check
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return Response("✅ Twilio Realtime Agent running", mimetype="text/plain")


# ---------------------------------------------------------------------
# 🚀 Run app
# ---------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print(f"🚀 Running on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)