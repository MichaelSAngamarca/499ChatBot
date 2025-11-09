import os
import signal
import threading
import time
import argparse
import pyttsx3
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from tools import client_tools
from connectivity_checker import check_internet_connectivity, safe_api_call
from offline_mode import OfflineMode
from wake_word_detector import WakeWordDetector
from hotkey_handler import HotkeyHandler

def speak(text, rate=150, volume=0.9):
    """Speak text using text-to-speech."""
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"TTS Error: {e}")

def initialize_online_mode():
    load_dotenv()
    agent_id = os.getenv("AGENT_ID")
    api_key = os.getenv("ELEVENLABS_API_KEY")
    
    if not api_key:
        print("Warning: No ElevenLabs API key found. Falling back to offline mode.")
        return None
    
    try:
        elevenlabs = ElevenLabs(api_key=api_key)
        conversation = Conversation(
            elevenlabs,
            agent_id,
            client_tools=client_tools,
            requires_auth=bool(api_key),
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda response: print(f"TalkAssist: {response}"),
            callback_agent_response_correction=lambda original, corrected: print(f"TalkAssist: {original} -> {corrected}"),
            callback_user_transcript=lambda transcript: print(f"User: {transcript}"),
        )
        return conversation
    except Exception as e:
        print(f"Error initializing online mode: {e}")
        return None

# Global variables for mode management
current_mode = None  # 'online' or 'offline'
online_conversation = None
offline_mode_instance = None
mode_thread = None
stop_monitoring = threading.Event()
mode_lock = threading.RLock()  # Reentrant lock to allow nested locking
conversation_ended_event = threading.Event()  # Signal when conversation ends naturally
should_exit_program = False  # Flag to exit the entire program

def run_online_mode_thread(conversation):
    """Run online mode in a separate thread."""
    global current_mode, online_conversation, conversation_ended_event
    try:
        print("Starting online conversation session...")
        conversation.start_session()
        conversation_id = conversation.wait_for_session_end()
        print(f"\nOnline conversation ended. Conversation ID: {conversation_id}")
        conversation_ended_event.set()
    except Exception as e:
        print(f"Error during online conversation: {e}")
        conversation_ended_event.set()
    finally:
        with mode_lock:
            if current_mode == 'online':
                current_mode = None
                online_conversation = None

def run_offline_mode_thread():
    """Run offline mode in a separate thread."""
    global current_mode, offline_mode_instance, conversation_ended_event
    try:
        offline_mode_instance.run()
        conversation_ended_event.set()
    except Exception as e:
        print(f"Error during offline mode: {e}")
        conversation_ended_event.set()
    finally:
        with mode_lock:
            if current_mode == 'offline':
                current_mode = None
                offline_mode_instance = None

def stop_current_mode():
    global current_mode, online_conversation, offline_mode_instance, mode_thread
    
    with mode_lock:  
        if current_mode == 'online' and online_conversation:
            try:
                print("Stopping online mode...")
                online_conversation.end_session()
                if mode_thread and mode_thread.is_alive():
                    mode_thread.join(timeout=2)
                online_conversation = None
                current_mode = None
                print("Online mode stopped.")
            except Exception as e:
                print(f"Error stopping online mode: {e}")
                current_mode = None
        
        elif current_mode == 'offline' and offline_mode_instance:
            try:
                print("Stopping offline mode...")
                offline_mode_instance.stop()
                if mode_thread and mode_thread.is_alive():
                    mode_thread.join(timeout=2)
                offline_mode_instance = None
                current_mode = None
                print("Offline mode stopped.")
            except Exception as e:
                print(f"Error stopping offline mode: {e}")
                current_mode = None

def start_online_mode():
    """Start online mode."""
    global current_mode, online_conversation, mode_thread
    
    with mode_lock:
        if current_mode == 'online':
            return  # Already running
        
        # Stop offline mode if running
        if current_mode == 'offline':
            stop_current_mode()  # RLock allows nested locking
            time.sleep(0.5)  # Brief pause for cleanup
        
        print("\n" + "="*60)
        print("Switching to ONLINE mode")
        print("="*60)
        
        conversation = initialize_online_mode()
        if conversation is None:
            print("Failed to initialize online mode. Staying in current mode.")
            return
        
        online_conversation = conversation
        current_mode = 'online'
        
        # Start online mode in a thread
        mode_thread = threading.Thread(target=run_online_mode_thread, args=(conversation,), daemon=True)
        mode_thread.start()
        print("Online mode started successfully.")

def start_offline_mode():
    """Start offline mode."""
    global current_mode, offline_mode_instance, mode_thread
    
    with mode_lock:
        if current_mode == 'offline':
            return  
        
        if current_mode == 'online':
            stop_current_mode() 
            time.sleep(0.5)  
        
        print("\n" + "="*60)
        print("Switching to OFFLINE mode")
        print("="*60)
        
        offline_mode_instance = OfflineMode()
        current_mode = 'offline'
        
        mode_thread = threading.Thread(target=run_offline_mode_thread, daemon=True)
        mode_thread.start()
        print("Offline mode started successfully.")

def monitor_connectivity():
    """Monitor connectivity and switch modes as needed."""
    global current_mode, conversation_ended_event, should_exit_program, mode_thread
    last_connectivity = None
    
    while not stop_monitoring.is_set() and not should_exit_program:
        try:
            is_connected = check_internet_connectivity()
            
            if last_connectivity is not None and is_connected != last_connectivity:
                if is_connected:
                    print("\n✓ Internet connection detected!")
                    if current_mode is None:
                        start_online_mode()
                else:
                    print("\n✗ Internet connection lost!")
                    if current_mode is None:
                        start_offline_mode()
            
            elif last_connectivity is None:
                if is_connected:
                    print("Internet connection detected. Starting online mode...")
                    start_online_mode()
                else:
                    print("No internet connection. Starting offline mode...")
                    start_offline_mode()
            
            last_connectivity = is_connected
            
            if conversation_ended_event.wait(timeout=5):
                conversation_ended_event.clear()
                if mode_thread and mode_thread.is_alive():
                    mode_thread.join(timeout=2)
                break
            
        except Exception as e:
            print(f"Error in connectivity monitoring: {e}")
            time.sleep(5)

def start_main_application(blocking=True, on_stop_callback=None):
    global stop_monitoring, conversation_ended_event, should_exit_program
    
    print("\n" + "="*60)
    print("Starting TalkAssist...")
    print("Monitoring connectivity and managing mode switching...")
    print("="*60 + "\n")
    
    stop_monitoring.clear()
    conversation_ended_event.clear()
    should_exit_program = False
    
    def monitor_with_callback():
        try:
            monitor_connectivity()
        finally:
            if on_stop_callback:
                on_stop_callback()
    
    monitor_thread = threading.Thread(target=monitor_with_callback, daemon=not blocking)
    monitor_thread.start()
    
    if blocking:
        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            should_exit_program = True
            stop_monitoring.set()
            stop_current_mode()
            if on_stop_callback:
                on_stop_callback()
            print("Shutdown complete. Goodbye!")
    else:
        return monitor_thread

def wait_for_wake_word_and_start():
    """Wait for wake word, then start the application. Returns True if should continue looping."""
    global should_exit_program
    
    print("="*60)
    print("Waiting for wake word activation...")
    print("Say 'hey talk assist' to start a conversation")
    print("Press Ctrl+C to exit the program")
    print("="*60 + "\n")
    
    speak("Say hey talk assist to start a conversation!")
    
    wake_detector = WakeWordDetector(wake_phrase="hey talk assist", model_size="base")
    
    try:
        wake_detected = wake_detector.wait_for_wake_word(verbose=True)
        
        if not wake_detected or should_exit_program:
            wake_detector.stop()
            return False
        
        wake_detector.stop()
        del wake_detector
        
        print("\n" + "="*60)
        print("Wake word detected! Starting TalkAssist...")
        print("="*60 + "\n")
        
        start_main_application()
        
        print("\n" + "="*60)
        print("Conversation ended. Returning to wake word detection...")
        print("="*60 + "\n")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        wake_detector.stop()
        should_exit_program = True
        return False
    except Exception as e:
        print(f"Error: {e}")
        wake_detector.stop()
        return True

def main(hotkey='ctrl+shift+a', skip_wake_word=False):
    global stop_monitoring, should_exit_program
    
    print("="*60)
    print("TalkAssist - Starting Application")
    print("="*60)
    print("Starting hotkey listener...")
    print(f"Press [{hotkey.upper()}] to activate TalkAssist")
    print("Press Ctrl+C to exit")
    print("="*60 + "\n")
    
    handler = HotkeyHandler(hotkey=hotkey)
    
    def on_hotkey_triggered():
        try:
            if skip_wake_word:
                start_main_application(blocking=True)
                return
            
            keep_listening = True
            while keep_listening and not should_exit_program:
                keep_listening = wait_for_wake_word_and_start()
        except Exception as e:
            print(f"Error while handling wake word workflow: {e}")
        finally:
            handler.reset_running_state()
    
    handler.set_callback(on_hotkey_triggered)
    
    try:
        handler.start_listening()
    except KeyboardInterrupt:
        handler.stop()
        print("\nShutdown complete. Goodbye!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TalkAssist - Voice Assistant with Hotkey Support')
    parser.add_argument('--hotkey-combo', type=str, default='ctrl+shift+a', 
                       help='Hotkey combination (default: ctrl+shift+a)')
    parser.add_argument('--skip-wake-word', action='store_true', 
                       help='Skip wake word detection and start directly')
    
    args = parser.parse_args()
    
    def signal_handler(sig, frame):
        print("\n\nReceived interrupt signal...")
        global stop_monitoring
        stop_monitoring.set()
        stop_current_mode()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    main(hotkey=args.hotkey_combo, skip_wake_word=args.skip_wake_word)