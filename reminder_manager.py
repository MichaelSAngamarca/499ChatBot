"""
Shared Reminder Manager
Handles reminder operations for both online and offline modes.
All reminders are stored in reminders.json and shared between modes.
"""
import json
import os
import re
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from time_parser import TimeParser
import threading

class ReminderManager:
    """Manages reminders for both online and offline modes."""
    
    def __init__(self, reminders_file="reminders.json", scheduler=None):
        self.reminders_file = reminders_file
        self.time_parser = TimeParser()
        self.reminders = []
        self.scheduler = scheduler
        self._lock = threading.Lock()
        self.load_reminders()
        
        # If no scheduler provided, create one
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            self._own_scheduler = True
        else:
            self._own_scheduler = False
    
    def load_reminders(self):
        """Load reminders from JSON file."""
        with self._lock:
            if os.path.exists(self.reminders_file):
                try:
                    with open(self.reminders_file, 'r') as f:
                        self.reminders = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading reminders: {e}")
                    self.reminders = []
            else:
                self.reminders = []
            
            # Schedule active reminders
            self._schedule_active_reminders()
    
    def save_reminders(self):
        """Save reminders to JSON file."""
        with self._lock:
            try:
                with open(self.reminders_file, 'w') as f:
                    json.dump(self.reminders, f, indent=4)
            except IOError as e:
                print(f"Error saving reminders: {e}")
    
    def _schedule_active_reminders(self):
        """Schedule all active reminders that haven't passed."""
        now = datetime.now()
        for reminder in self.reminders:
            if reminder.get("active", True):
                reminder_time = datetime.fromisoformat(reminder['time'])
                if reminder_time > now:
                    job_id = f"reminder_{reminder['id']}"
                    try:
                        # Remove existing job if it exists
                        try:
                            self.scheduler.remove_job(job_id)
                        except:
                            pass
                        # Add new job
                        self.scheduler.add_job(
                            self.trigger_reminder,
                            'date',
                            run_date=reminder_time,
                            args=[reminder['id'], reminder['text']],
                            id=job_id
                        )
                    except Exception as e:
                        print(f"Error scheduling reminder {reminder['id']}: {e}")
    
    def get_next_reminder_id(self):
        """Get the next available reminder ID."""
        if not self.reminders:
            return 1
        return max(r.get('id', 0) for r in self.reminders) + 1
    
    def set_reminder(self, text, callback_speak=None):
        """
        Set a reminder from natural language text.
        
        Args:
            text: Natural language text like "remind me to call mom tomorrow at 3pm"
            callback_speak: Optional callback function to speak responses (for offline mode)
        
        Returns:
            tuple: (success: bool, message: str, reminder_id: int or None)
        """
        # Clean and preprocess text
        raw_lower = text.lower().strip()
        cleaned = self._fix_transcription_errors(raw_lower)
        
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
        m = trigger_prefix.match(cleaned)
        if m:
            cleaned = cleaned[m.end():].strip()
        
        cleaned = re.sub(r'^\bmorrow\b', 'tomorrow', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bto\s+morrow\b', 'tomorrow', cleaned, flags=re.IGNORECASE)
        
        if not cleaned:
            msg = "What would you like me to remind you about?"
            if callback_speak:
                callback_speak(msg)
            return False, msg, None
        
        # Preprocess day parts
        cleaned = self._daypart_for_parser(cleaned)
        
        # Parse time
        parsed_time, success, error = self.time_parser.parse_time(cleaned)
        
        if not success:
            # Default to 1 minute from now if parsing fails
            reminder_time = datetime.now() + timedelta(minutes=1)
            reminder_text = cleaned
            msg = "I could not understand the time. Setting reminder for 1 minute from now."
            if callback_speak:
                callback_speak(msg)
        else:
            reminder_time = parsed_time
            converted_text = self.time_parser._convert_words_to_numbers(cleaned)
            reminder_text = self._extract_task_from_text(converted_text)
            if not reminder_text or len(reminder_text) < 3:
                reminder_text = cleaned
            reminder_text = re.sub(r'\b(we\s+)?remind\s+me(\s+to)?\b', '', reminder_text, flags=re.IGNORECASE).strip()
            reminder_text = re.sub(r'^(for|to)\s+', '', reminder_text, flags=re.IGNORECASE).strip()
        
        # Create reminder
        reminder_id = self.get_next_reminder_id()
        reminder = {
            "id": reminder_id,
            "text": reminder_text,
            "time": reminder_time.isoformat(),
            "active": True,
        }
        
        with self._lock:
            self.reminders.append(reminder)
            self.save_reminders()
        
        # Schedule reminder
        job_id = f"reminder_{reminder_id}"
        try:
            self.scheduler.add_job(
                self.trigger_reminder,
                'date',
                run_date=reminder_time,
                args=[reminder_id, reminder_text],
                id=job_id
            )
        except Exception as e:
            print(f"Error scheduling reminder: {e}")
        
        human_time = self.time_parser.format_time_human(reminder_time)
        msg = f"Reminder set for {human_time}: {reminder_text}"
        if callback_speak:
            callback_speak(msg)
        
        return True, msg, reminder_id
    
    def list_reminders(self, callback_speak=None):
        """
        List all active reminders.
        
        Args:
            callback_speak: Optional callback function to speak responses
        
        Returns:
            str: Formatted list of reminders
        """
        now = datetime.now()
        active_reminders = [
            r for r in self.reminders 
            if r.get("active", True) and datetime.fromisoformat(r['time']) > now
        ]
        
        if not active_reminders:
            msg = "You have no active reminders."
            if callback_speak:
                callback_speak(msg)
            return msg
        
        active_reminders.sort(key=lambda r: datetime.fromisoformat(r['time']))
        count = len(active_reminders)
        
        msg_parts = [f"You have {count} active reminder{'s' if count > 1 else ''}"]
        for i, reminder in enumerate(active_reminders, 1):
            reminder_time = datetime.fromisoformat(reminder['time'])
            time_str = reminder_time.strftime("%I:%M %p on %B %d")
            msg_parts.append(f"Reminder {i} at {time_str}: {reminder['text']}")
        
        full_msg = ". ".join(msg_parts)
        if callback_speak:
            # Speak each reminder separately for better TTS
            callback_speak(msg_parts[0])
            for part in msg_parts[1:]:
                callback_speak(part)
        
        return full_msg
    
    def delete_reminder_by_id(self, reminder_id):
        """Delete a reminder by ID."""
        with self._lock:
            reminder = None
            for r in self.reminders:
                if r['id'] == reminder_id:
                    reminder = r
                    break
            
            if not reminder:
                return False, "Reminder not found."
            
            job_id = f"reminder_{reminder_id}"
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                print(f"Warning: could not remove job from scheduler: {e}")
            
            reminder['active'] = False
            self.save_reminders()
            return True, f"Reminder deleted: {reminder['text']}"
    
    def delete_reminder_by_number(self, number, callback_speak=None):
        """Delete a reminder by its position in the active reminders list."""
        now = datetime.now()
        active_reminders = sorted(
            [r for r in self.reminders if r.get("active", True) and datetime.fromisoformat(r['time']) > now],
            key=lambda r: datetime.fromisoformat(r['time'])
        )
        
        if not active_reminders:
            msg = "You have no active reminders to delete."
            if callback_speak:
                callback_speak(msg)
            return False, msg
        
        if number < 1 or number > len(active_reminders):
            msg = f"Invalid reminder number. You have {len(active_reminders)} active reminders. Please choose a number between 1 and {len(active_reminders)}."
            if callback_speak:
                callback_speak(msg)
            return False, msg
        
        reminder_to_delete = active_reminders[number - 1]
        success, msg = self.delete_reminder_by_id(reminder_to_delete['id'])
        if success and callback_speak:
            callback_speak(f"Reminder number {number} deleted: {reminder_to_delete['text']}")
        return success, msg
    
    def clear_all_reminders(self, callback_speak=None):
        """Clear all reminders."""
        with self._lock:
            for reminder in self.reminders:
                job_id = f"reminder_{reminder['id']}"
                try:
                    self.scheduler.remove_job(job_id)
                except:
                    pass
            
            self.reminders = []
            self.save_reminders()
        
        msg = "All reminders have been cleared."
        if callback_speak:
            callback_speak(msg)
        return msg
    
    def trigger_reminder(self, reminder_id, reminder_text):
        """Trigger a reminder when its time is reached."""
        # This will be called by the scheduler
        # We need to notify the user - this will be handled by the mode-specific code
        print(f"REMINDER: {reminder_text}")
        
        # Mark reminder as inactive
        with self._lock:
            for reminder in self.reminders:
                if reminder['id'] == reminder_id:
                    reminder['active'] = False
                    break
            self.save_reminders()
        
        # Call the global speak function if available
        try:
            from main import speak
            speak(f"Reminder: {reminder_text}")
        except ImportError:
            # If main is not available, just print
            print(f"REMINDER: {reminder_text}")
        except Exception as e:
            print(f"Error speaking reminder: {e}")
    
    def _fix_transcription_errors(self, text):
        """Fix common transcription errors."""
        corrections = {
            r'\bat10d\b': 'attend',
            r'\bat tend\b': 'attend',
            r'\batt end\b': 'attend',
            r'\ba10d\b': 'attend',
            r'\b2day\b': 'today',
            r'\bto morrow\b': 'tomorrow',
            r'\b2 morrow\b': 'tomorrow',
            r'\b2morrow\b': 'tomorrow',
            r'\btomorow\b': 'tomorrow',
            r'\btommorow\b': 'tomorrow',
            r'\btommorrow\b': 'tomorrow',
            r'\bmee ting\b': 'meeting',
            r'\bmeating\b': 'meeting',
            r'\b(\d+)\s*p\s*m\b': r'\1 PM',
            r'\b(\d+)\s*a\s*m\b': r'\1 AM',
            r'\b(\d+)\s*p\.?\s?m\.?\b': r'\1 PM',
            r'\b(\d+)\s*a\.?\s?m\.?\b': r'\1 AM',
            r'\b(\d{1,2})\.(\d{2})\b': r'\1:\2',
        }
        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r'\b(a\.?m\.?|p\.?m\.?)\b\.', r'\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _daypart_for_parser(self, s: str) -> str:
        """Preprocess day parts before sending to time parser."""
        def has_explicit_time(txt: str) -> bool:
            return (
                re.search(r'\b\d{1,2}[:.]\d{2}\s*(a\.?m\.?|p\.?m\.?)\b', txt, re.IGNORECASE)
                or re.search(r'\b\d{1,2}\s*(a\.?m\.?|p\.?m\.?)\b', txt, re.IGNORECASE)
                or re.search(r'\b\d{1,2}[:.]\d{2}\b', txt)
            )
        
        DAYPART_DEFAULTS = {
            "morning": "9 am",
            "afternoon": "3 pm",
            "evening": "7 pm",
            "night": "9 pm",
        }
        
        s = re.sub(r'\btonight\b', 'today night', s, flags=re.IGNORECASE)
        
        for part, clock in DAYPART_DEFAULTS.items():
            s = re.sub(
                rf'\btomorrow\s+{part}\b',
                f'tomorrow at {clock}' if not has_explicit_time(s) else 'tomorrow',
                s,
                flags=re.IGNORECASE
            )
            s = re.sub(
                rf'\btoday\s+{part}\b',
                f'today at {clock}' if not has_explicit_time(s) else 'today',
                s,
                flags=re.IGNORECASE
            )
            s = re.sub(
                rf'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+{part}\b',
                lambda m: f"{m.group(1)} at {clock}" if not has_explicit_time(s) else m.group(0),
                s,
                flags=re.IGNORECASE
            )
        
        if not has_explicit_time(s) and not re.search(r'\b(today|tomorrow|next|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', s, re.IGNORECASE):
            for part, clock in DAYPART_DEFAULTS.items():
                s = re.sub(rf'\b{part}\b', f'today at {clock}', s, flags=re.IGNORECASE)
        
        return s
    
    def _extract_task_from_text(self, text):
        """Extract the task description from text, removing time information."""
        time_patterns = [
            r'in\s+\d+\s+(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\b',
            r'\btomorrow\s+at\s+',
            r'\btoday\s+at\s+',
            r'\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+',
            r'\bat\s+\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)\b',
            r'\b\d{1,2}[:.]?\d{0,2}\s*(am|pm|a\.m\.|p\.m\.)\b',
            r'\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(morning|afternoon|evening|night|tonight)\b',
            r'\bnext\s+week\b',
        ]
        
        task = text
        for pattern in time_patterns:
            task = re.sub(pattern, '', task, flags=re.IGNORECASE)
        
        task = re.sub(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', task, flags=re.IGNORECASE)
        task = re.sub(r'\b(tomorrow|today)\b', '', task, flags=re.IGNORECASE)
        task = re.sub(r'\b(to\s+)?morrow\b', '', task, flags=re.IGNORECASE)
        task = re.sub(r'[.,!?]+', '', task)
        task = re.sub(r'\s+', ' ', task)
        task = task.strip()
        task = re.sub(r'^(to|at|on|in)\s+', '', task, flags=re.IGNORECASE)
        task = re.sub(r'\s+(to|at|on|in)$', '', task, flags=re.IGNORECASE)
        
        if len(task) < 3 or task.isdigit():
            return ""
        
        return task
    
    def shutdown(self):
        """Shutdown the reminder manager and scheduler if we own it."""
        if self._own_scheduler and self.scheduler:
            self.scheduler.shutdown()


# Global reminder manager instance
_global_reminder_manager = None
_reminder_manager_lock = threading.Lock()

def get_reminder_manager(scheduler=None):
    """Get or create the global reminder manager instance."""
    global _global_reminder_manager
    with _reminder_manager_lock:
        if _global_reminder_manager is None:
            _global_reminder_manager = ReminderManager(scheduler=scheduler)
        return _global_reminder_manager

