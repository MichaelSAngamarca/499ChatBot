from flask import Flask, render_template, request, jsonify
from tools import get_weather_info, get_region_info, get_date_info, search_web
import os
import subprocess

# Initialize Flask app
app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static"
)

# Home route -> loads GUI
@app.route("/")
def index():
    return render_template("index.html")

# Chat API route -> handles user messages
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

def extract_location(text):
    """A quick helper to find a location keyword from user input."""
    # Basic version: looks for 'in <place>'
    if "in " in text:
        return text.split("in ")[1].strip()
    return None

if __name__ == "__main__":
    app.run(debug=True)
