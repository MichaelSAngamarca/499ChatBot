To Run The Demo.

First you need to install everything in the reqiurments.txt file which includes:
elevenlabs
pyaudio
openai
dotenv
pillow
langchain_community

You can do a simple install by doing the command uv pip install -r requirements.txt. if this does not work then you can simply manually install by doing pip  install then the package name. 

Id recomended you setup the virtual enviroment by simply doing python -m venv venv which sets up a local virtual enviroment. 

Once you pull this repo you can then simply run the main.py file by doing python .\main.py to run the program. It should then start the chatbot and you should hear the chatbot speak. it already by default has microphone access due to pyaudio so permissions as of right now are set to alwasys on by defualt. 

You can ask it some questons but as of right now does not do much. To end the conversation simply say something that mentions that you want to end the converstaion and it should do it automatically. 
NOTE**
Make sure you have the virtual enviroment activated by running .\venv\Scripts\activate 

### Offline Mode (Local Processing)
- ***tTime queries***: "What time is it?"
- ***Date Queries***: "What is the date?", "What day is today?"
- **Natural language reminders**
-  "Remind me to call mom in 4 hours"
-  "Remind me to take my medecine tomorrow at 3pm"
-  "Set a reminder Monday at 9am to eat breakfast"
- **List reminder**: "what are my reminders?"
- **Storage**: Reminders are saved acroos sessions

### Supported time formats
- Today: "today at 5pm"
- Tomorrow: "tomorrow", "tomorrow at 3pm"
- Weekdays: "Monday at 9am", "next friday at 2pm"
- Specific times: "at 5pm", "11:55am", "16:30"

### Ending session
Say: "goodbye", "bye", "quit", "stop"

### What we used so far to make these implementations
- **speech recognition**: OpenAI Whisper(small model: 500MB)
- **Text to speech**: pyttsx3
- **Reminder**: APScheduler for scheduling, JSON fopr storage
- **Time parsing**: Custom natural language parser



###

The microphone is always on when the program is running
The audio recordings are temporaly saved and deleted after the transcription
Offline mode wors without internet connection

