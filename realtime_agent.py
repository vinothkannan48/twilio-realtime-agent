import os
import json
import asyncio
import websockets
from flask import Flask, request, Response
from flask_sock import Sock 
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# --- ENVIRONMENT ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))

app = Flask(__name__)
sock = Sock(app)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- ROUTE TO INITIATE OUTBOUND CALL ---
@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    if not to:
        return {"error": "Missing 'to' parameter"}, 400

    call = twilio_client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        twiml=f"""
            <Response>
                <Connect>
                    <Stream url="{PUBLIC_URL}/media-stream" />
                </Connect>
            </Response>
        """,
    )
    print(f"📞 Outbound realtime call started to {to}")
    return {"sid": call.sid}, 200


# --- TWILIO MEDIA STREAM HANDLER ---
@app.route("/media-stream", methods=["POST"])
def media_stream():
    """Tell Twilio to open a realtime WebSocket to our public ngrok tunnel."""
    # Ensure PUBLIC_URL exists and starts with https
    public_https_url = PUBLIC_URL.strip()

    # Convert https://... → wss://...
    if public_https_url.startswith("https://"):
        ws_url = public_https_url.replace("https://", "wss://", 1)
    elif public_https_url.startswith("http://"):
        ws_url = public_https_url.replace("http://", "ws://", 1)
    else:
        ws_url = f"wss://{public_https_url}"

    ws_url = f"{ws_url}/twilio-stream"  # append the path

    print(f"🎧 Twilio will stream audio to: {ws_url}")

    # Return valid TwiML
    response = f"""
        <Response>
            <Connect>
                <Stream url="{ws_url}" />
            </Connect>
        </Response>
    """
    return Response(response.strip(), mimetype="text/xml")


# --- WEBSOCKET HANDLER (BIDIRECTIONAL STREAM) ---
@sock.route("/twilio-stream")
async def twilio_stream(ws):
    """
    Handle bidirectional audio between Twilio and OpenAI Realtime.
    """
    print("🔗 Twilio media stream connected.")
    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
            extra_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        ) as openai_ws:
            print("🤖 Connected to OpenAI Realtime API.")

            async def forward_twilio_to_openai():
                async for message in ws:
                    try:
                        data = json.loads(message)
                        if data.get("event") == "media":
                            audio_chunk = data["media"]["payload"]
                            await openai_ws.send(
                                json.dumps(
                                    {"type": "input_audio_buffer.append", "audio": audio_chunk}
                                )
                            )
                    except Exception as e:
                        print("Error forwarding Twilio→OpenAI:", e)

            async def forward_openai_to_twilio():
                async for message in openai_ws:
                    try:
                        data = json.loads(message)
                        if data.get("type") == "output_audio_buffer.append":
                            audio_chunk = data["audio"]
                            await ws.send(
                                json.dumps({"event": "media", "media": {"payload": audio_chunk}})
                            )
                    except Exception as e:
                        print("Error forwarding OpenAI→Twilio:", e)

            await asyncio.gather(forward_twilio_to_openai(), forward_openai_to_twilio())

    except Exception as e:
        print("WebSocket error:", e)
    finally:
        print("❌ Twilio stream disconnected.")


if __name__ == "__main__":
    print(f"🚀 Starting Flask (Realtime Mode) on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT)