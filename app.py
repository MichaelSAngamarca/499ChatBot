from flask import Flask, render_template, request, jsonify
import subprocess

app = Flask(
    __name__,
    template_folder="frontend/templates",
    static_folder="frontend/static"
)

# Home route -> loads GUI
@app.route("/")
def index():
    return render_template("index.html")

# API route -> simulates user asking a question
@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("message", "")

    if "weather" in user_input.lower():
        response = "It's 72°F and sunny right now."
    elif "time" in user_input.lower():
        response = "The current time is 3:45 PM."
    else:
        response = "I'm not sure, but I can look that up for you."

    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
