"""
Offline mode
This file contains code to enable offline functionality for the chatbot.
It includes modules for speech recognition, text-to-speech, and local processing.
"""
import os
from pydoc import text
import whisper
import pyttsx3
import pyaudio
import wave
import numpy as np
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import json
import threading
from time_parser import TimeParser

class OfflineMode:
    def __init__(self):
        print ("loading the whisper model...")
        self.whisper_model = whisper.load_model("small")  # there are base, small, medium, large models

        self.tts_rate = 150
        self.tts_volume = 0.9

        self.time_parser = TimeParser()
        # initializing the scheduler here
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
    

        # the reminders will be saved in a json file
        self.reminders_file = "reminders.json"
        self.load_reminders()

    def speak(self, text):
        # This function is to convert text to speech
        print(f"TalkAssist: {text}")
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', self.tts_rate)
            engine.setProperty('volume', self.tts_volume)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"TTS Error: {e}")

    def check_audio_level(self, audio_data):
        #checking the volume level of audio data
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        volume = np.abs(audio_np).mean()
        return volume

    def listen(self, max_duration=7, silence_duration=3.5):
        # is able to record audio with automatic silence detection. Will stp recording after silence_durantion seconds of silence
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        frames = []
        total_volume = 0
        num_chunks = 0
        silence_chunks = 0
        max_silence_chunks = int((self.RATE / self.CHUNK) * silence_duration)
        speech_detected = False
        min_speech_chunks = int((self.RATE / self.CHUNK) * 0.5)

        for i in range(0, int(self.RATE / self.CHUNK * max_duration)):
            data = stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)

            # Checking the volume level
            volume = self.check_audio_level(data)
            total_volume += volume
            num_chunks += 1

            # this will show when sound is detected
            if volume > 200:  # speech detected
                print("█", end="", flush=True)
                silence_chunks = 0
                speech_detected = True
            else:
                print("░", end="", flush=True)
                if speech_detected:
                    silence_chunks += 1
            if speech_detected and silence_chunks >= max_silence_chunks:
                if num_chunks >= min_speech_chunks:
                    print("(stopped - silence detected)")
                    break

        print()

        # for stopping the recording
        stream.stop_stream()
        stream.close()
        audio.terminate()

        avg_volume = total_volume / num_chunks if num_chunks > 0 else 0
        print(f"Average audio level: {avg_volume:.0f}")

        # Checking if the audio was too low to process
        # if no speech was detected
        # saved audio to a temp file and transcribe it
        if avg_volume < 100:
            return ""
        temp_file = "temp_audio.wav"
        wf = wave.open(temp_file, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(audio.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames))
        wf.close()

        # transcribing the audio using whisper
        print("Transcribing the audio...")
        result = self.whisper_model.transcribe(temp_file, language="en", fp16=False)
        text = result['text'].strip()

        # Clean up temp file with error handling
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            print(f"Warning: Could not delete temp file: {e}")

        if text:
            print(f"✓ You said: {text}")
        else:
            self.speak("I didn't catch that. Please try again.")

        return text
    
    # function to process the voice commands
    def process_command(self, text):
        text_lower = text.lower()
        # for exit commands
        if any(word in text_lower for word in ["goodbye", "exit", "quit", "stop", "bye", "see you", "later", "end", "terminate", " end conversation", "okay,thank you"]):
            self.speak("Goodbye! Have a great day!")
            return False
        # for time queries
        if any (word in text_lower for word in ["time", "what's the time", "current time", "tell me the time", "time now", "what time is it", "can you tell me the time"]):
            current_time = datetime.now().strftime("%I:%M %p")
            self.speak(f"The current time is {current_time}")
            return True
        # for date queries
        if any (word in text_lower for word in ["date", "what's the date", "current date", "what day is today", "tell me the date", "what is today", "what day is it", "can you tell me the date"]):
            current_date = datetime.now().strftime(" %A, %B %d, %Y")
            self.speak(f"Today is {current_date}")
            return True
        
         #getting the list of reminders
        if any (word in text_lower for word in ["list reminders", "show reminders", "what are my reminders", "my reminders"]):
            self.list_reminders()
            return True
        
        # for setting reminders
        if any (word in text_lower for word in ["remind me to", "set a reminder for", "set a reminder to", "reminde me", "set a reminder", "remind me at", "remind me in", "remember to", "set a reminder in"]):
            self.set_reminder(text)
            return True
        
        # for deleting all reminders
        if any(word in text_lower for word in ["clear reminders","delete all reminders", "remove all reminders", "cancel all reminders"]):
            self.clear_all_reminders()
            return True
       
        #what to say if the command is not recognized
        self.speak("I'm sorry, I can only tell the time, date, set reminders, and list reminders in offline mode.")
        return True
    
    def set_reminder(self, text):
        text_lower = text.lower()
        for phrase in ["remind me to", "remind me", "set a reminder to", "set a reminder", "remember to"]:
            text_lower = text_lower.replace(phrase, "", 1)
        text_lower = text_lower.strip()
        if not text_lower:
            self.speak("What would you like me to remind you about?")
            return
        parsed_time, success, error = self.time_parser.parse_time(text_lower)
        if not success:
            self.speak("I could not understand the time. setting reminder for 1 minute for now.") # this is for demo, will be uppdated later
            from datetime import timedelta
            reminder_time = datetime.now() + timedelta(minutes=1)

            reminder_text = text_lower
        else:
            reminder_time = parsed_time
            converted_text = self.time_parser._convert_words_to_numbers(text_lower)
            reminder_text = self._extract_task_from_text(converted_text)
            if not reminder_text:
                reminder_text = text_lower
        reminder_id = len(self.reminders) + 1
        reminder = {
            "id": reminder_id,
            "text": reminder_text,
            "time": reminder_time.isoformat(),
            "active": True
        }
        self.reminders.append(reminder)
        self.save_reminders()
        self.scheduler.add_job(self.trigger_reminder, 'date', run_date=reminder_time, args=[reminder_id, reminder_text], id=f"reminder_{reminder_id}")
        human_time = self.time_parser.format_time_human(reminder_time)
        self.speak(f"Reminder set for {human_time}: {reminder_text}")

    #function to clear or cancel all reminders
    def clear_all_reminders(self):
        for reminder in self.reminders:
            job_id = f"reminder_{reminder['id']}"
            try: 
                self.scheduler.remove_job(job_id)
            except:
                pass

        self.reminders = []
        self.save_reminders()
        self.speak("all reminders have been cleared")


    #helper fucntion to help extracting the task description from text with time infos
    def _extract_task_from_text(self, text):
        import re
        time_patterns = [
            r'in\s+\d+\s+\w+\.?',
            r'\btomorrow\b\s*(at)?',
            r'\btoday\b\s*(at)?', 
            r'at\s+\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)?',
            r'\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\.?',
            r'(mon|tue|wed|thu|fri|sat|sun)\.?',
            r'next\s+\w+\.?',
            r'\b(am|pm|a\.m\.|p\.m\.)\b',
        ]

        task = text
        for pattern in time_patterns:
            task = re.sub(pattern, '', task, flags=re.IGNORECASE)
            # making sure to erase any extra spaces and "at"
        task = re.sub(r'[.,!?]+', '', task)
        task = re.sub(r'\s+', ' ', task)
        task = task.strip()
        task = re.sub(r'^(to|at)\s+', '', task, flags=re.IGNORECASE)
        return task
    
    def trigger_reminder(self, reminder_id, reminder_text):
        #this function is for triggering the reminder
        self.speak(f"Reminder: {reminder_text}")
        for reminder in self.reminders:
            if reminder['id'] == reminder_id:
                reminder['active'] = False
        self.save_reminders()

    def list_reminders(self):
        # listing all active reminders
        # filtering active reminders
        now = datetime.now()
        active_reminders = [r for r in self.reminders if r.get("active", True) and datetime.fromisoformat(r['time']) > now]

        if not active_reminders:
            self.speak("You have no active reminders.")
            return

        count = len(active_reminders)
        self.speak(f"You have {count} active reminder{'s' if count > 1 else ''}")

        for reminder in active_reminders:
            reminder_time = datetime.fromisoformat(reminder['time'])
            time_str = reminder_time.strftime("%I:%M %p on %B %d")
            self.speak(f"Reminder at {time_str}: {reminder['text']}")

    def load_reminders(self):
        #getting the reminders from the json file that was created
        if os.path.exists(self.reminders_file):
            with open(self.reminders_file, 'r') as f:
                self.reminders = json.load(f)

            for reminder in self.reminders:
                if reminder.get("active", True):
                    reminder_time = datetime.fromisoformat(reminder['time'])
                    if reminder_time > datetime.now():
                        self.scheduler.add_job(self.trigger_reminder, 'date', run_date=reminder_time, args=[reminder['id'], reminder['text']], id=f"reminder_{reminder['id']}") 
        else:
            self.reminders = [] # Initialize an empty list if the file doesn't exist

    def save_reminders(self):
        with open (self.reminders_file, 'w') as f:
            json.dump(self.reminders, f, indent=4)

    def run(self):
        print("\n" + "="*60)
        print("TalkAssist - Offline Mode")
        print("="*60)
        print("Commands: time, date, 'remind me to...', 'list reminders', 'goodbye'")
        print("="*60 + "\n")

        self.speak("Hello! I am TalkAssist running in offline mode. How can I assist you today?")

        while True:
            try:
                user_text = self.listen()

                if not user_text or user_text.strip() == "":
                    #print("No speech detected. Please try again.\n")
                    continue

                should_continue = self.process_command(user_text)

                if not should_continue:
                    break
            except KeyboardInterrupt:
                print("\n\nInterrupted by the user (Ctrl+C)")
                self.speak("Goodbye! Have a great day!")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                import traceback
                traceback.print_exc()
                self.speak("Sorry, I encountered an error. Please try again.")

        print("\nShutting down...")
        self.scheduler.shutdown()
        print("Goodbye!")

if __name__ == "__main__":
    offline_mode = OfflineMode()
    offline_mode.run()



