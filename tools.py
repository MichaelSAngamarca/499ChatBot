import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from elevenlabs.conversational_ai.conversation import ClientTools
from langchain_community.tools import DuckDuckGoSearchRun
from metar import Metar
load_dotenv()
weatherAPIKey = os.getenv("WEATHER_API_KEY")

def get_region_info(parameters=None):
    try:
        city = parameters.get("city") if parameters else None
        if not city:
            geoData = requests.get("https://ipapi.co/json/").json()
            city = geoData.get("city")

        if not city:
            return {"error": "Could not determine city"}

        search = DuckDuckGoSearchRun()
        query = f"{city} airport ICAO code"
        result = search.run(query)
        lines = result.split()
        icao = None
        for token in lines:
            if len(token) == 4 and token.isalpha():
                icao = token.upper()
                break
        if not icao:
            return {"error": f"Could not determine ICAO code for {city}"}

        # Download latest METAR report
        metar_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"
        response = requests.get(metar_url)
        if response.status_code != 200:
            return {"error": f"Could not retrieve METAR data for {icao}"}

        metar_text = response.text.strip().split("\n")[-1]
        obs = Metar.Metar(metar_text)

        temp_c = obs.temp.value("C") if obs.temp else None
        humidity = obs.rel_humidity()
        condition = obs.present_weather() or obs.sky_conditions()
        time = obs.time if obs.time else datetime.utcnow()

        return {
            "location": f"{city} ({icao})",
            "local_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": f"{temp_c:.1f}°C" if temp_c else "N/A",
            "humidity": f"{humidity:.0f}%" if humidity else "N/A",
            "conditions": condition or "Unknown"
        }
    except Exception as e:
        return {"error": str(e)}
def search_web(parameters):
    query = parameters.get("query") if parameters else None
    if not query:
        return "No query provided."
    search = DuckDuckGoSearchRun()
    return search.run(query)

def save_to_txt(parameters):
    filename = parameters.get("filename")
    data = parameters.get("data")

    if not filename or not data:
        return "Missing filename or data."

    try:
        with open(filename, "a", encoding="utf-8") as file:
            file.write(f"{data}\n")
        return f"Data saved to {filename}"
    except Exception as e:
        return f"Error saving file: {e}"

client_tools = ClientTools()
client_tools.register("searchWeb", search_web)
client_tools.register("saveToTxt", save_to_txt)
client_tools.register("getRegionInfo", get_region_info)
