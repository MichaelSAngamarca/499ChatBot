import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from elevenlabs.conversational_ai.conversation import ClientTools
from langchain_community.tools import DuckDuckGoSearchRun
from connectivity_checker import check_internet_connectivity, safe_api_call
import time
load_dotenv()
def handle_api_failure(error_msg, fallback_msg="I'm sorry, I'm having trouble connecting to the internet. Please check your connection and try again."):
    
    if not check_internet_connectivity():
        return "I'm currently offline and cannot access this information. Please check your internet connection."
    return f"Error: {error_msg}. {fallback_msg}"

def get_current_time(parameters):
    location = parameters.get("location")
    
    if location:
        if not check_internet_connectivity():
            return handle_api_failure("No internet connection available")
        
        try:
            geo_url = "https://nominatim.openstreetmap.org/search"
            geo_params = {"q": location, "format": "json"}
            geo_res = requests.get(geo_url, params=geo_params, headers={"User-Agent": "TalkAssistBot/1.0"}).json()

            if not geo_res:
                return f"Could not find location: {location}"

            lat = geo_res[0]["lat"]
            lon = geo_res[0]["lon"]

            tz_url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lon}"
            tz_res = requests.get(tz_url).json()
            timezone = tz_res.get("timeZone", None)

            if not timezone:
                return f"Could not find timezone for {location}."

            time_url = f"https://timeapi.io/api/Time/current/zone?timeZone={timezone}"
            time_res = requests.get(time_url).json()

            current_time = time_res.get("dateTime", None)
            if not current_time:
                return f"Could not get current time for {location}."

            return f"The current time in {location} ({timezone}) is {current_time}"

        except Exception as e:
            return f"Error getting time for {location}: {e}"
    else:
        try:
            now = datetime.now()
            formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
            timezone_name = time.tzname[0] if time.tzname[0] else "local timezone"
            return f"The current local time is {formatted_time} ({timezone_name})"
        except Exception as e:
            return f"Error getting local time: {e}"

def get_region_info(parameters):
    return get_current_time(parameters)

def get_weather_info(parameters):
    location = parameters.get("location")
    if not location:
        return "Please provide a location."
    
    if not check_internet_connectivity():
        return handle_api_failure("No internet connection available")

    try:
        geo_url = "https://nominatim.openstreetmap.org/search"
        geo_params = {"q": location, "format": "json"}
        #geo_res = requests.get(geo_url, params=geo_params).json()
        geo_res = requests.get(geo_url, params=geo_params, headers={"User-Agent": "TalkAssistBot/1.0"}).json()


        if not geo_res:
            return f"Could not find location: {location}"

        lat = geo_res[0]["lat"]
        lon = geo_res[0]["lon"]

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
        )
        weather_res = requests.get(weather_url).json()

        current_weather = weather_res.get("current_weather", {})
        if not current_weather:
            return f"Could not retrieve weather for {location}."

        temperature = current_weather.get("temperature")
        windspeed = current_weather.get("windspeed")
        conditions = current_weather.get("weathercode")

        weather_map = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "freezing fog", 51: "light drizzle", 53: "moderate drizzle",
            55: "dense drizzle", 61: "light rain", 63: "moderate rain", 65: "heavy rain",
            71: "light snow", 73: "moderate snow", 75: "heavy snow", 95: "thunderstorm",
        }

        condition_text = weather_map.get(conditions, "unknown conditions")
        return (
            f"The current weather in {location} is {condition_text} "
            f"with a temperature of {temperature}°C and windspeed of {windspeed} km/h."
        )

    except Exception as e:
        return f"Error getting weather info: {e}"
    
def get_date_info(parameters):
    location = parameters.get("location")
    
    if location:
        if not check_internet_connectivity():
            return handle_api_failure("No internet connection available")
        
        try:
            geo_url = "https://nominatim.openstreetmap.org/search"
            geo_params = {"q": location, "format": "json"}
            geo_res = requests.get(geo_url, params=geo_params, headers={"User-Agent": "TalkAssistBot/1.0"}).json()

            if not geo_res:
                return f"Could not find location: {location}"

            lat = geo_res[0]["lat"]
            lon = geo_res[0]["lon"]

            tz_url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lon}"
            tz_res = requests.get(tz_url).json()
            timezone = tz_res.get("timeZone", None)

            if not timezone:
                return f"Could not find timezone for {location}."

            time_url = f"https://timeapi.io/api/Time/current/zone?timeZone={timezone}"
            time_res = requests.get(time_url).json()

            date_string = time_res.get("date", None)
            day_of_week = time_res.get("dayOfWeek", None)

            if not date_string:
                return f"Could not get date for {location}."

            return f"Today's date in {location} ({timezone}) is {day_of_week}, {date_string}."
        except Exception as e:
            return f"Error getting date for {location}: {e}"
    else:
        try:
            now = datetime.now()
            formatted_date = now.strftime("%A, %B %d, %Y")
            timezone_name = time.tzname[0] if time.tzname[0] else "local timezone"
            return f"Today's date is {formatted_date} ({timezone_name})"
        except Exception as e:
            return f"Error getting local date: {e}"

def search_web(parameters):
    query = parameters.get("query") if parameters else None
    if not query:
        return "No query provided."
    
    if not check_internet_connectivity():
        return handle_api_failure("No internet connection available")
    
    try:
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as e:
        return handle_api_failure(f"Search failed: {str(e)}")

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

def set_reminder(parameters):
    """
    Set a reminder from natural language text.
    Use this tool when the user wants to create a reminder or be reminded about something.
    The text should include both what to be reminded about and when (e.g., "remind me to call mom tomorrow at 3pm").
    
    Parameters:
        text (string, required): The reminder text with time information. 
            Examples: 
            - "remind me to call mom tomorrow at 3pm"
            - "set a reminder to buy groceries in 2 hours"
            - "remember to attend the meeting on Friday at 10am"
    """
    import json
    import os
    import re
    from datetime import datetime, timedelta
    from time_parser import TimeParser
    from main import reminder_scheduler, speak
    
    text = parameters.get("text") if parameters else None
    if not text:
        return "Please provide the reminder text. For example: 'remind me to call mom tomorrow at 3pm'"
    
    reminders_file = "reminders.json"
    time_parser = TimeParser()
    
    # Load existing reminders
    if os.path.exists(reminders_file):
        with open(reminders_file, 'r') as f:
            reminders = json.load(f)
    else:
        reminders = []
    
    # Clean and parse the reminder text (similar to offline mode)
    raw_lower = text.lower().strip()
    cleaned = text.strip()
    
    # Remove trigger prefixes
    trigger_prefix = re.compile(
        r'^(?:'
        r'remind\s+me(?:\s+to)?'
        r'|set\s+(?:a\s+)?reminder(?:\s+to)?'
        r'|remember\s+to'
        r'|we\s+(?:need|have)\s+to'
        r')\s+',
        re.IGNORECASE
    )
    m = trigger_prefix.match(cleaned.lower())
    if m:
        cleaned = cleaned[m.end():].strip()
    
    cleaned = re.sub(r'^\bmorrow\b', 'tomorrow', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bto\s+morrow\b', 'tomorrow', cleaned, flags=re.IGNORECASE)
    
    if not cleaned:
        return "What would you like me to remind you about?"
    
    # Preprocess day parts (similar to offline mode)
    def daypart_for_parser(s: str) -> str:
        def has_explicit_time(txt: str) -> bool:
            return (
                re.search(r'\b\d{1,2}[:.]\d{2}\s*(a\.?m\.?|p\.?m\.?)\b', txt, re.IGNORECASE)
                or re.search(r'\b\d{1,2}\s*(a\.?m\.?|p\.?m\.?)\b', txt, re.IGNORECASE)
                or re.search(r'\b\d{1,2}[:.]\d{2}\b', txt)
            )
        DAYPART_DEFAULTS = {"morning": "9 am", "afternoon": "3 pm", "evening": "7 pm", "night": "9 pm"}
        s = re.sub(r'\btonight\b', 'today night', s, flags=re.IGNORECASE)
        for part, clock in DAYPART_DEFAULTS.items():
            s = re.sub(rf'\btomorrow\s+{part}\b', f'tomorrow at {clock}' if not has_explicit_time(s) else 'tomorrow', s, flags=re.IGNORECASE)
            s = re.sub(rf'\btoday\s+{part}\b', f'today at {clock}' if not has_explicit_time(s) else 'today', s, flags=re.IGNORECASE)
            s = re.sub(rf'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+{part}\b',
                      lambda m: f"{m.group(1)} at {clock}" if not has_explicit_time(s) else m.group(0), s, flags=re.IGNORECASE)
        if not has_explicit_time(s) and not re.search(r'\b(today|tomorrow|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', s, re.IGNORECASE):
            for part, clock in DAYPART_DEFAULTS.items():
                s = re.sub(rf'\b{part}\b', f'today at {clock}', s, flags=re.IGNORECASE)
        return s
    
    cleaned = daypart_for_parser(cleaned)
    
    # Parse time
    parsed_time, success, error = time_parser.parse_time(cleaned)
    
    if not success:
        reminder_time = datetime.now() + timedelta(minutes=1)
        reminder_text = cleaned
        message = "I could not understand the time. Setting reminder for 1 minute from now."
    else:
        reminder_time = parsed_time
        converted_text = time_parser._convert_words_to_numbers(cleaned)
        
        # Extract task from text
        def extract_task_from_text(text):
            time_patterns = [
                r'in\s+\d+\s+(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b',
                r'\btomorrow\s+at\s+', r'\btoday\s+at\s+',
                r'\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+',
                r'\bat\s+\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)\b',
                r'\b\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)\b',
                r'\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
                r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
                r'\b(morning|afternoon|evening|night|tonight)\b', r'\bnext\s+week\b',
            ]
            task = text
            for pattern in time_patterns:
                task = re.sub(pattern, '', task, flags=re.IGNORECASE)
            task = re.sub(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', task, flags=re.IGNORECASE)
            task = re.sub(r'\b(tomorrow|today)\b', '', task, flags=re.IGNORECASE)
            task = re.sub(r'\b(to\s+)?morrow\b', '', task, flags=re.IGNORECASE)
            task = re.sub(r'[.,!?]+', '', task)
            task = re.sub(r'\s+', ' ', task).strip()
            task = re.sub(r'^(to|at|on|in)\s+', '', task, flags=re.IGNORECASE)
            task = re.sub(r'\s+(to|at|on|in)$', '', task, flags=re.IGNORECASE)
            return task if len(task) >= 3 and not task.isdigit() else ""
        
        reminder_text = extract_task_from_text(converted_text)
        if not reminder_text or len(reminder_text) < 3:
            reminder_text = cleaned
        reminder_text = re.sub(r'\b(we\s+)?remind\s+me(\s+to)?\b', '', reminder_text, flags=re.IGNORECASE).strip()
        reminder_text = re.sub(r'^(for|to)\s+', '', reminder_text, flags=re.IGNORECASE).strip()
        message = ""
    
    # Get next reminder ID
    reminder_id = max([r.get('id', 0) for r in reminders], default=0) + 1
    
    # Create reminder
    reminder = {
        "id": reminder_id,
        "text": reminder_text,
        "time": reminder_time.isoformat(),
        "active": True,
    }
    
    reminders.append(reminder)
    
    # Save to JSON
    with open(reminders_file, 'w') as f:
        json.dump(reminders, f, indent=4)
    
    # Schedule reminder
    def trigger_reminder(reminder_id, reminder_text):
        speak(f"Reminder: {reminder_text}")
        # Mark as inactive
        if os.path.exists(reminders_file):
            with open(reminders_file, 'r') as f:
                reminders = json.load(f)
            for r in reminders:
                if r['id'] == reminder_id:
                    r['active'] = False
            with open(reminders_file, 'w') as f:
                json.dump(reminders, f, indent=4)
    
    reminder_scheduler.add_job(
        trigger_reminder,
        'date',
        run_date=reminder_time,
        args=[reminder_id, reminder_text],
        id=f"reminder_{reminder_id}"
    )
    
    human_time = time_parser.format_time_human(reminder_time)
    return f"Reminder set for {human_time}: {reminder_text}"

def list_reminders(parameters):
    """
    List all active reminders that haven't been triggered yet.
    Use this tool when the user asks to see their reminders, list reminders, or check what reminders they have.
    No parameters required.
    """
    import json
    import os
    from datetime import datetime
    
    reminders_file = "reminders.json"
    
    if not os.path.exists(reminders_file):
        return "You have no active reminders."
    
    with open(reminders_file, 'r') as f:
        reminders = json.load(f)
    
    now = datetime.now()
    active_reminders = [
        r for r in reminders 
        if r.get("active", True) and datetime.fromisoformat(r['time']) > now
    ]
    
    if not active_reminders:
        return "You have no active reminders."
    
    active_reminders.sort(key=lambda r: datetime.fromisoformat(r['time']))
    count = len(active_reminders)
    
    result = [f"You have {count} active reminder{'s' if count > 1 else ''}"]
    for i, reminder in enumerate(active_reminders, 1):
        reminder_time = datetime.fromisoformat(reminder['time'])
        time_str = reminder_time.strftime("%I:%M %p on %B %d")
        result.append(f"Reminder {i} at {time_str}: {reminder['text']}")
    
    return ". ".join(result)

def delete_reminder(parameters):
    """
    Delete a reminder by its number in the list.
    Use this tool when the user wants to cancel, delete, or remove a reminder.
    First use listReminders to see the reminder numbers, then use this tool with the number.
    
    Parameters:
        number (integer, required): The reminder number (1-based index from the list).
            Get this number by first calling listReminders to see all reminders with their numbers.
    """
    import json
    import os
    from datetime import datetime
    from main import reminder_scheduler
    
    reminders_file = "reminders.json"
    number = parameters.get("number") if parameters else None
    
    if number is None:
        return "Please provide the reminder number to delete. Use 'list reminders' first to see the numbers."
    
    try:
        number = int(number)
    except (ValueError, TypeError):
        return "Please provide a valid reminder number."
    
    if not os.path.exists(reminders_file):
        return "You have no active reminders to delete."
    
    with open(reminders_file, 'r') as f:
        reminders = json.load(f)
    
    now = datetime.now()
    active_reminders = sorted(
        [r for r in reminders if r.get("active", True) and datetime.fromisoformat(r['time']) > now],
        key=lambda r: datetime.fromisoformat(r['time'])
    )
    
    if not active_reminders:
        return "You have no active reminders to delete."
    
    if number < 1 or number > len(active_reminders):
        return f"Invalid reminder number. You have {len(active_reminders)} active reminders. Please choose a number between 1 and {len(active_reminders)}."
    
    reminder_to_delete = active_reminders[number - 1]
    reminder_id = reminder_to_delete['id']
    
    # Remove from scheduler
    job_id = f"reminder_{reminder_id}"
    try:
        reminder_scheduler.remove_job(job_id)
    except:
        pass
    
    # Mark as inactive
    for reminder in reminders:
        if reminder['id'] == reminder_id:
            reminder['active'] = False
            break
    
    # Save to JSON
    with open(reminders_file, 'w') as f:
        json.dump(reminders, f, indent=4)
    
    return f"Reminder number {number} deleted: {reminder_to_delete['text']}"

client_tools = ClientTools()
client_tools.register("searchWeb", search_web)
client_tools.register("saveToTxt", save_to_txt)
client_tools.register("getCurrentTime", get_current_time)
client_tools.register("getRegionInfo", get_region_info)
client_tools.register("getWeatherInfo",get_weather_info)
client_tools.register("getDateInfo", get_date_info)
client_tools.register("setReminder", set_reminder)
client_tools.register("listReminders", list_reminders)
client_tools.register("deleteReminder", delete_reminder)