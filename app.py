from flask import Flask, render_template, request, jsonify, send_file
from tools import get_weather_info, get_region_info, get_date_info, search_web
from io import BytesIO
from elevenlabs import ElevenLabs
import os
import re
from dotenv import load_dotenv

# Load API key
load_dotenv()
api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs = ElevenLabs(api_key=api_key)

# Initialize Flask app
app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static"
)

# Home route
@app.route("/")
def index():
    return render_template("index.html")

# Reminders route
@app.route("/reminders")
def reminders():
    return render_template("reminders.html")

# Chat route
@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("message", "").lower()

    # Handle intent
    if "weather" in user_input:
        location = extract_location(user_input)
        if location:
            response = get_weather_info({"location": location})
            pretty = location.title()
            response = response.replace(location.lower(), pretty)
        else:
            response = "Please specify a location."
    elif "time" in user_input or "timezone" in user_input:
        location = extract_location(user_input)
        response = get_region_info({"location": location}) if location else "Please specify a location."
        #if location:
        #    response = get_region_info({"location": location})
        #    pretty = location.title()
        #    response = response.replace(location.lower(), pretty)
        #    response = response.replace("2025-", "").replace("T", " ").replace("Z", "")
        #else:
        #    response = "Please specify a location."
    elif "date" in user_input:
        location = extract_location(user_input)
        response = get_date_info({"location": location})
    elif "search" in user_input or "find" in user_input:
        query = user_input.replace("search", "").replace("find", "").strip()
        response = search_web({"query": query}) if query else "Please tell me what to search for."
    else:
        response = "I'm not sure how to help with that yet."

    return jsonify({"response": response})

# Speech route
@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # Use ElevenLabs API
        result = elevenlabs.text_to_speech.convert(
            voice_id="alloy",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            text=text
        )

        audio_bytes = result.content

        return send_file(
            BytesIO(audio_bytes),
            mimetype="audio/mpeg",
            as_attachment=False
        )
    except Exception as e:
        print("Error in /speak:", e)
        return jsonify({"error": str(e)}), 500

# Location extraction helper
def extract_location(text):
    """Extracts a location after the word 'in', stripping punctuation."""
    match = re.search(r"\bin\s+([a-zA-Z\s]+)", text)
    if match:
        location = match.group(1).strip().rstrip("?.!,")
        return location
    return None

# --- Run the app ---
if __name__ == "__main__":
    app.run(debug=True)
