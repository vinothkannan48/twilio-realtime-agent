import os
import json
import base64
import io
import asyncio
import websockets
import soundfile as sf
import numpy as np
from flask import Flask, request, Response
from flask_sock import Sock
from dotenv import load_dotenv
from twilio.rest import Client
from pydub import AudioSegment

load_dotenv()

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER  = os.getenv("TWILIO_FROM_NUMBER")
PUBLIC_URL          = os.getenv("PUBLIC_URL")

app = Flask(__name__)
sock = Sock(app)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ---------------------------------------------------------------------
#  Twilio -> greet + open websocket
# ---------------------------------------------------------------------
@app.route("/media-stream", methods=["POST"])
def media_stream():
    twiml = f"""
    <Response>
        <Connect>
            <Stream url="wss://{PUBLIC_URL.replace('https://','')}/twilio-stream" />
        </Connect>
    </Response>
    """
    return Response(twiml.strip(), mimetype="text/xml")

# ---------------------------------------------------------------------
#  Twilio websocket endpoint
# ---------------------------------------------------------------------
@sock.route("/twilio-stream")
def twilio_stream(ws):
    print("🔗 Twilio connected")
    stream_sid = None

    async def handle_audio():
        """Inner async task: connect to OpenAI Realtime and relay audio"""
        uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
        async with websockets.connect(
            uri,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            },
        ) as ai_ws:
            print("🤖 Connected to OpenAI Realtime")

            # Initial system message (bilingual prompt)
            await ai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions":
                        "You are a friendly voice assistant that detects "
                        "whether the speaker talks Tamil or English and "
                        "responds in that language, naturally and briefly.",
                    "modalities": ["audio"],
                    "conversation": []
                }
            }))

            while True:
                msg = ws.receive()
                if msg is None:
                    break
                data = json.loads(msg)
                event = data.get("event")

                if event == "start":
                    nonlocal stream_sid
                    stream_sid = data["start"]["streamSid"]
                    print("🎧 Twilio stream started:", stream_sid)

                elif event == "media":
                    # Incoming μ-law base64 audio -> PCM float32
                    b = base64.b64decode(data["media"]["payload"])
                    ulaw = np.frombuffer(b, dtype=np.uint8)
                    pcm = AudioSegment(
                        ulaw.tobytes(),
                        frame_rate=8000,
                        sample_width=1,
                        channels=1
                    ).set_frame_rate(16000).set_sample_width(2)
                    # Send raw 16-bit PCM to OpenAI
                    await ai_ws.send(b"--audio-data--" + pcm.raw_data)

                elif event == "stop":
                    print("🛑 Twilio stream stopped")
                    break

                # Receive AI audio
                try:
                    reply = await asyncio.wait_for(ai_ws.recv(), timeout=0.01)
                    rdata = json.loads(reply)
                    if rdata.get("type") == "response.output_audio.delta":
                        pcm_bytes = base64.b64decode(rdata["delta"])
                        seg = AudioSegment(
                            pcm_bytes,
                            frame_rate=16000,
                            sample_width=2,
                            channels=1
                        ).set_frame_rate(8000).set_sample_width(1)
                        payload = base64.b64encode(seg.raw_data).decode("utf-8")
                        ws.send(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": payload}
                        }))
                except Exception:
                    pass

    asyncio.run(handle_audio())

# ---------------------------------------------------------------------
#  Outbound call starter
# ---------------------------------------------------------------------
@app.route("/make_call", methods=["POST"])
def make_call():
    to = request.form.get("to")
    if not to:
        return {"error": "Missing 'to' number"}, 400

    call = twilio_client.calls.create(
        to=to,
        from_=TWILIO_FROM_NUMBER,
        url=f"{PUBLIC_URL}/media-stream",
        method="POST"
    )
    print("📞 Outbound realtime call:", call.sid)
    return {"sid": call.sid}, 200

# ---------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)