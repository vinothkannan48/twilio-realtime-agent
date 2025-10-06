import os, io, json, base64
from flask import Flask, request, Response
from flask_sock import Sock
from twilio.rest import Client
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
PUBLIC_URL = os.getenv("PUBLIC_URL")

app = Flask(__name__)
sock = Sock(app)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route("/", methods=["GET"])
def index():
    return "✅ Flask Realtime Twilio Agent running", 200

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

@sock.route("/twilio-stream")
def twilio_stream(ws):
    print("🔗 Twilio media stream connected")
    stream_sid = None
    try:
        while True:
            msg = ws.receive()
            if not msg:
                break
            data = json.loads(msg)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                print(f"🎧 Stream started: {stream_sid}")

                # --- Generate greeting speech ---
                tts = gTTS("Hello Vinod! This is your test agent speaking.", lang="en")
                mp3_buf = io.BytesIO()
                tts.write_to_fp(mp3_buf)
                mp3_buf.seek(0)

                # --- Convert MP3 -> µ-law 8 kHz mono ---
                audio = AudioSegment.from_file(mp3_buf, format="mp3")
                ulaw = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2).set_sample_width(1)
                raw = ulaw.raw_data
                payload = base64.b64encode(raw).decode("utf-8")

                # --- Send back to Twilio ---
                ws.send(json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload}
                }))
                print("🗣️ Sent greeting audio to Twilio")

            elif event == "stop":
                print("🛑 Stream stopped")
                break

    except Exception as e:
        print("⚠️ WebSocket error:", e)

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)