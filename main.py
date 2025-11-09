import os
import signal
import threading
import time
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from tools import client_tools
from connectivity_checker import check_internet_connectivity, safe_api_call
from offline_mode import OfflineMode
from wake_word_detector import WakeWordDetector

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

def run_online_mode_thread(conversation):
    """Run online mode in a separate thread."""
    global current_mode, online_conversation
    try:
        print("Starting online conversation session...")
        conversation.start_session()
        conversation_id = conversation.wait_for_session_end()
        print(f"Online conversation ended. Conversation ID: {conversation_id}")
    except Exception as e:
        print(f"Error during online conversation: {e}")
    finally:
        with mode_lock:
            if current_mode == 'online':
                current_mode = None
                online_conversation = None

def run_offline_mode_thread():
    """Run offline mode in a separate thread."""
    global current_mode, offline_mode_instance
    try:
        offline_mode_instance.run()
    except Exception as e:
        print(f"Error during offline mode: {e}")
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
    global current_mode
    last_connectivity = None
    
    while not stop_monitoring.is_set():
        try:
            is_connected = check_internet_connectivity()
            
            if last_connectivity is not None and is_connected != last_connectivity:
                if is_connected:
                    print("\n✓ Internet connection detected!")
                    start_online_mode()
                else:
                    print("\n✗ Internet connection lost!")
                    start_offline_mode()
            
            elif last_connectivity is None:
                if is_connected:
                    print("Internet connection detected. Starting online mode...")
                    start_online_mode()
                else:
                    print("No internet connection. Starting offline mode...")
                    start_offline_mode()
            
            last_connectivity = is_connected
            
            stop_monitoring.wait(5)
            
        except Exception as e:
            print(f"Error in connectivity monitoring: {e}")
            time.sleep(5)

def main():
    global stop_monitoring
    
    print("="*60)
    print("TalkAssist - Starting Application")
    print("="*60)
    print("Waiting for wake word activation...")
    print("="*60 + "\n")
    
    # Initialize wake word detector
    wake_detector = WakeWordDetector(wake_phrase="hey talk assist", model_size="base")
    
    # Wait for wake word before starting main functionality
    try:
        wake_detected = wake_detector.wait_for_wake_word(verbose=True)
        
        if not wake_detected:
            print("Wake word detection stopped. Exiting...")
            return
        
        print("\n" + "="*60)
        print("Wake word detected! Starting TalkAssist...")
        print("Monitoring connectivity and managing mode switching...")
        print("="*60 + "\n")
        
        # Clean up wake detector
        wake_detector.stop()
        del wake_detector
        
    except KeyboardInterrupt:
        print("\n\nShutting down before activation...")
        wake_detector.stop()
        return
    
    # Start connectivity monitoring in a separate thread
    monitor_thread = threading.Thread(target=monitor_connectivity, daemon=False)
    monitor_thread.start()
    
    try:
        monitor_thread.join()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        stop_monitoring.set()
        stop_current_mode()
        print("Shutdown complete. Goodbye!")

if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\nReceived interrupt signal...")
        global stop_monitoring
        stop_monitoring.set()
        stop_current_mode()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    main()