from flask import Flask, render_template, request, jsonify, send_file
from tools import get_weather_info, get_region_info, get_date_info, search_web
from io import BytesIO
from elevenlabs import ElevenLabs, play
import os
import subprocess


from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs = ElevenLabs(api_key=api_key)


app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static"
)

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("message", "").lower()

    # Decide which tool to use based on message keywords
    if "weather" in user_input.lower():
        location = extract_location(user_input)
        response = get_weather_info({"location": location}) if location else "Please specify a location."
    elif "time" in user_input or "timezone" in user_input:
        location = extract_location(user_input)
        response = get_region_info({"location": location}) if location else "Please specify a location."
    elif "date" in user_input:
        location = extract_location(user_input)
        response = get_date_info({"location": location})
    elif "search" in user_input or "find" in user_input:
        query = user_input.replace("search", "").replace("find", "").strip()
        response = search_web({"query": query}) if query else "Please tell me what to search for."
    else:
        response = "I'm not sure how to help with that yet."

    return jsonify({"response": response})

@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        audio = elevenlabs.text_to_speech.convert(
            voice_id="Rachel",  
            output_format="mp3_44100_128",
            text=text
        )

        return send_file(
            BytesIO(audio),
            mimetype="audio/mpeg",
            as_attachment=False
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_location(text):
    """A quick helper to find a location keyword from user input."""
    if "in " in text:
        return text.split("in ")[1].strip()
    return None

if __name__ == "__main__":
    app.run(debug=True)
