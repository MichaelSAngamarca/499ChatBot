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
#from app import app
from werkzeug.serving import make_server

# Shared speech function
def speak(text, rate=150, volume=0.9):
    """Speak text using text-to-speech."""
    if not text or text.strip() == "":
        return
    if text.lower().startswith(("error processing message", "sorry, the bot", "tts error")):
        print(f"(Skipping TTS for internal message: {text})")
        return
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"TTS Error: {e}")

# Online mode initialization
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
            requires_auth=bool(api_key),.\main.
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
flask_thread = None 
flask_server = None
switching_modes = threading.Event()  # Flag to indicate we're in the middle of switching modes

# Helper functions for Flask
def get_or_create_conversation():
    """Ensure we have a valid online conversation object."""
    global online_conversation
    if online_conversation is None:
        online_conversation = initialize_online_mode()
    
    if online_conversation:
        try:
            if not getattr(online_conversation, "_ws", None) or not online_conversation._ws.connected:
                print("Starting or reconnecting conversation session...")
                try:
                    online_conversation.start_session()
                    # Wait up to 5s for connection
                    for _ in range(50):
                        if getattr(online_conversation, "_ws", None) and online_conversation._ws.connected:
                            break
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("Conversation websocket failed to connect.")
                except Exception as e:
                    print(f"Error starting conversation session: {e}")
                    online_conversation = None
                    return None
            
        except Exception as e:
            print(f"Error starting session: {e}")
            online_conversation = None
    
    return online_conversation

def handle_user_message(message):
    conversation = get_or_create_conversation()
    if conversation is None:
        return "Sorry, the bot is currently offline or could not initialize."
    
    try:
        response = conversation.send_user_message(message)
        return response or "Sorry, no response received."
    except RuntimeError as e:
        if "websocket failed to connect" in str(e):
            return "Sorry, the bot session is not ready yet."
        return f"Error processing message: {e}"

# Mode control
def run_online_mode_thread(conversation):
    """Run online mode in a separate thread."""
    global current_mode, online_conversation, conversation_ended_event, switching_modes
    try:
        print("Starting online conversation session...")
        conversation.start_session()
        conversation_id = conversation.wait_for_session_end()
        print(f"\nOnline conversation ended. Conversation ID: {conversation_id}")
        # Only set event if we're still in online mode AND not switching modes
        with mode_lock:
            if current_mode == 'online' and not switching_modes.is_set():
                conversation_ended_event.set()
    except Exception as e:
        print(f"Error during online conversation: {e}")
        import traceback
        traceback.print_exc()
        # Only set event if we're still in online mode AND not switching modes
        with mode_lock:
            if current_mode == 'online' and not switching_modes.is_set():
                conversation_ended_event.set()
    finally:
        # Only clean up if we're still the active conversation (not already switched)
        with mode_lock:
            # Only clear if this conversation is still the active one
            if online_conversation is conversation:
                if current_mode == 'online':
                    current_mode = None
                    online_conversation = None

def run_offline_mode_thread():
    """Run offline mode in a separate thread."""
    global current_mode, offline_mode_instance, conversation_ended_event, switching_modes
    try:
        offline_mode_instance.run()
        # Only set event if we're still in offline mode AND not switching modes
        with mode_lock:
            if current_mode == 'offline' and not switching_modes.is_set():
                conversation_ended_event.set()
    except Exception as e:
        print(f"Error during offline mode: {e}")
        # Only set event if we're still in offline mode AND not switching modes
        with mode_lock:
            if current_mode == 'offline' and not switching_modes.is_set():
                conversation_ended_event.set()
    finally:
        with mode_lock:
            if current_mode == 'offline':
                current_mode = None
                offline_mode_instance = None

def stop_current_mode():
    global current_mode, online_conversation, offline_mode_instance, mode_thread, conversation_ended_event, switching_modes
    
    with mode_lock:
        # Set flag to indicate we're switching modes
        switching_modes.set()
        conversation_ended_event.clear()
        
        if current_mode == 'online' and online_conversation:
            try:
                print("Stopping online mode...")
                # Store reference before clearing
                conv_to_stop = online_conversation
                thread_to_join = mode_thread
                
                # Clear global reference first to prevent race conditions
                online_conversation = None
                current_mode = None
                
                # Now safely end the session with comprehensive error handling
                try:
                    # Try to stop audio interface first to prevent stream errors
                    if hasattr(conv_to_stop, 'audio_interface') and conv_to_stop.audio_interface:
                        try:
                            # Check if stream is open before stopping
                            if hasattr(conv_to_stop.audio_interface, 'in_stream'):
                                stream = conv_to_stop.audio_interface.in_stream
                                if stream and hasattr(stream, '_stream') and stream._stream:
                                    try:
                                        # Check if stream is active before stopping
                                        import pyaudio
                                        if stream._stream.is_active():
                                            stream.stop_stream()
                                    except (OSError, AttributeError) as e:
                                        # Stream already closed or not open - this is fine
                                        pass
                        except Exception as e:
                            # Audio interface cleanup errors are expected during mode switch
                            pass
                    
                    # Try to end session, but suppress expected errors
                    try:
                        conv_to_stop.end_session()
                    except Exception as e:
                        # Suppress expected errors during cleanup (websocket/SSL/audio stream errors)
                        error_str = str(e)
                        error_type = type(e).__name__
                        # These errors are expected when switching modes - suppress them
                        expected_errors = [
                            'ConnectionClosed',
                            'SSLEOF',
                            'Stream not open',
                            'sent 1000',
                            'no close frame',
                            'EOF occurred',
                            'violation of protocol'
                        ]
                        if not any(err in error_type or err in error_str for err in expected_errors):
                            # Only log unexpected errors
                            print(f"Warning: Error ending session: {error_type}")
                except Exception as e:
                    # Catch any errors in the cleanup block itself
                    pass
                
                # Wait for thread to finish (with shorter timeout since we're suppressing errors)
                if thread_to_join and thread_to_join.is_alive():
                    thread_to_join.join(timeout=2)  # Reduced timeout since we're handling errors
                    if thread_to_join.is_alive():
                        # Thread didn't finish, but that's okay - we've cleaned up what we can
                        pass
                
                # Additional cleanup - ensure websocket is closed (suppress errors)
                try:
                    if hasattr(conv_to_stop, '_ws') and conv_to_stop._ws:
                        # Check if websocket is still connected before trying to close
                        try:
                            if hasattr(conv_to_stop._ws, 'connected') and conv_to_stop._ws.connected:
                                if hasattr(conv_to_stop._ws, 'close'):
                                    conv_to_stop._ws.close()
                        except (ConnectionError, AttributeError):
                            # Already closed or closing - this is fine
                            pass
                except Exception:
                    # Websocket cleanup errors are expected - suppress
                    pass
                
                # Clear the reference
                try:
                    del conv_to_stop
                except:
                    pass
                print("Online mode stopped.")
            except Exception as e:
                # Final catch-all - ensure we always clean up state
                error_type = type(e).__name__
                if 'ConnectionClosed' not in error_type and 'SSLEOF' not in error_type:
                    print(f"Error stopping online mode: {error_type}")
                # Ensure cleanup even on error
                online_conversation = None
                current_mode = None
        
        elif current_mode == 'offline' and offline_mode_instance:
            try:
                print("Stopping offline mode...")
                # Store reference before clearing
                offline_to_stop = offline_mode_instance
                thread_to_join = mode_thread
                
                # Clear global reference first
                offline_mode_instance = None
                current_mode = None
                
                # Now safely stop offline mode
                offline_to_stop.stop()
                
                # Wait for thread to finish
                if thread_to_join and thread_to_join.is_alive():
                    thread_to_join.join(timeout=5)  # Increased timeout
                    if thread_to_join.is_alive():
                        print("Warning: Offline mode thread did not finish in time")
                
                print("Offline mode stopped.")
            except Exception as e:
                print(f"Error stopping offline mode: {e}")
                import traceback
                traceback.print_exc()
                # Ensure cleanup even on error
                offline_mode_instance = None
                current_mode = None

def start_online_mode():
    """Start online mode."""
    global current_mode, online_conversation, mode_thread, conversation_ended_event, switching_modes
    
    with mode_lock:
        if current_mode == 'online':
            switching_modes.clear()  # Clear flag if already in online mode
            return  # Already running
        
        # Stop any existing mode first
        if current_mode == 'offline':
            stop_current_mode()  # RLock allows nested locking
            time.sleep(0.5)  # Brief pause for cleanup
        elif current_mode == 'online':
            # This shouldn't happen, but clean up just in case
            stop_current_mode()
            time.sleep(0.5)
        
        # Ensure any lingering conversation object is cleaned up
        if online_conversation is not None:
            try:
                print("Cleaning up lingering conversation object...")
                if hasattr(online_conversation, 'end_session'):
                    try:
                        online_conversation.end_session()
                    except:
                        pass
                if hasattr(online_conversation, '_ws') and online_conversation._ws:
                    try:
                        if hasattr(online_conversation._ws, 'close'):
                            online_conversation._ws.close()
                    except:
                        pass
            except Exception as e:
                print(f"Warning: Error cleaning up lingering conversation: {e}")
            finally:
                online_conversation = None
        
        # Ensure mode thread is fully stopped
        if mode_thread and mode_thread.is_alive():
            print("Waiting for previous mode thread to finish...")
            mode_thread.join(timeout=2)
        
        # Additional cleanup pause
        time.sleep(0.3)
        
        print("\n" + "="*60)
        print("Switching to ONLINE mode")
        print("="*60)
        
        conversation = initialize_online_mode()
        if conversation is None:
            print("Failed to initialize online mode. Staying in current mode.")
            switching_modes.clear()
            return
        
        online_conversation = conversation
        current_mode = 'online'
        
        # Clear any lingering events before starting new mode
        conversation_ended_event.clear()
        
        # Start online mode in a thread
        mode_thread = threading.Thread(target=run_online_mode_thread, args=(conversation,), daemon=True)
        mode_thread.start()
        print("Online mode started successfully.")
        
        # Clear event again after a brief moment to catch any immediate thread events
        time.sleep(0.2)
        conversation_ended_event.clear()
        switching_modes.clear()  # Clear flag after mode switch is complete

def start_offline_mode():
    """Start offline mode."""
    global current_mode, offline_mode_instance, mode_thread, conversation_ended_event, switching_modes
    
    with mode_lock:
        if current_mode == 'offline':
            switching_modes.clear()  # Clear flag if already in offline mode
            return  
        
        # Stop any existing mode first
        if current_mode == 'online':
            stop_current_mode() 
            time.sleep(0.5)  
        elif current_mode == 'offline':
            # This shouldn't happen, but clean up just in case
            stop_current_mode()
            time.sleep(0.5)
        
        # Ensure any lingering offline mode instance is cleaned up
        if offline_mode_instance is not None:
            try:
                print("Cleaning up lingering offline mode instance...")
                offline_mode_instance.stop()
            except Exception as e:
                print(f"Warning: Error cleaning up lingering offline instance: {e}")
            finally:
                offline_mode_instance = None
        
        # Ensure mode thread is fully stopped
        if mode_thread and mode_thread.is_alive():
            print("Waiting for previous mode thread to finish...")
            mode_thread.join(timeout=2)
        
        # Additional cleanup pause
        time.sleep(0.3)
        
        print("\n" + "="*60)
        print("Switching to OFFLINE mode")
        print("="*60)
        
        offline_mode_instance = OfflineMode()
        current_mode = 'offline'
        
        # Clear any lingering events before starting new mode
        conversation_ended_event.clear()
        
        mode_thread = threading.Thread(target=run_offline_mode_thread, daemon=True)
        mode_thread.start()
        print("Offline mode started successfully.")
        
        # Clear event again after a brief moment to catch any immediate thread events
        time.sleep(0.2)
        conversation_ended_event.clear()
        switching_modes.clear()  # Clear flag after mode switch is complete

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
                    # Switch to online mode if we're offline or not in any mode
                    if current_mode == 'offline' or current_mode is None:
                        start_online_mode()
                else:
                    print("\n✗ Internet connection lost!")
                    # Switch to offline mode if we're online or not in any mode
                    if current_mode == 'online' or current_mode is None:
                        start_offline_mode()
            
            elif last_connectivity is None:
                if is_connected:
                    print("Internet connection detected. Starting online mode...")
                    start_online_mode()
                else:
                    print("No internet connection. Starting offline mode...")
                    start_offline_mode()
            
            last_connectivity = is_connected
            
            # Check if conversation ended naturally (not due to mode switch)
            # Only break if the event is set AND we're not in any mode AND not switching modes
            if conversation_ended_event.wait(timeout=5):
                # Double-check the mode after the event is set (with lock to avoid race conditions)
                with mode_lock:
                    # Event was set (wait returned True), now check mode and switching flag before clearing
                    current_mode_check = current_mode
                    is_switching = switching_modes.is_set()
                    conversation_ended_event.clear()
                
                # Only exit if we're not in any mode, not switching modes, and event was set (natural conversation end)
                if current_mode_check is None and not is_switching:
                    print("\nConversation ended naturally. Returning to wake word detection...")
                    if mode_thread and mode_thread.is_alive():
                        mode_thread.join(timeout=2)
                    break
                # Otherwise, continue monitoring (mode switch happened or event was spurious)
                else:
                    if is_switching:
                        print("(Ignoring conversation_ended_event - mode switch in progress)")
                    else:
                        print(f"(Ignoring conversation_ended_event - still in {current_mode_check} mode, continuing monitoring)")
            
        except Exception as e:
            print(f"Error in connectivity monitoring: {e}")
            time.sleep(5)

# Start Flask
def start_flask_server(host="0.0.0.0", port=5001):
    from app import app
    global flask_server, flask_thread
    server = make_server(host, port, app)
    flask_server = server

    def serve():
        print(f"Flask server started at http://localhost:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Flask serve loop exited: {e}")

    t = threading.Thread(target=serve)
    t.start()
    flask_thread = t
    return server, t

def start_main_application(blocking=True, on_stop_callback=None):
    global stop_monitoring, conversation_ended_event, should_exit_program
    
    print("\n" + "="*60)
    print("Starting TalkAssist...")
    print("Monitoring connectivity and managing mode switching...")
    print("="*60 + "\n")
    
    stop_monitoring.clear()
    conversation_ended_event.clear()
    should_exit_program = False

    server, thread = start_flask_server()
    
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
            # rely on signal handler
            pass
    else:
        return monitor_thread, thread

# Track if we've already spoken the initial message for the current hotkey press
_initial_message_spoken = False
_last_message_time = 0

def wait_for_wake_word_and_start():
    """Wait for wake word, then start the application. Returns True if should continue looping."""
    global should_exit_program, _initial_message_spoken, _last_message_time
    
    print("="*60)
    print("Waiting for wake word activation...")
    print("Say 'hey talk assist' to start a conversation")
    print("Press Ctrl+C to exit the program")
    print("="*60 + "\n")
    
    # Only speak the message the first time (when hotkey is first pressed)
    # Not when returning from a conversation, and not if we just spoke it recently
    current_time = time.time()
    if not _initial_message_spoken and (current_time - _last_message_time) > 2.0:
        speak("Say hey talk assist to start a conversation!")
        _initial_message_spoken = True
        _last_message_time = current_time
    
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

    if skip_wake_word:
        # Directly start the app without hotkey
        start_main_application(blocking=True)
        return

    print("Starting hotkey listener...")
    print(f"Press [{hotkey.upper()}] to activate TalkAssist")
    print("Press Ctrl+C to exit")
    print("="*60 + "\n")
    
    handler = HotkeyHandler(hotkey=hotkey)
    
    def on_hotkey_triggered():
        global _initial_message_spoken, _last_message_time
        try:
            if skip_wake_word:
                start_main_application(blocking=True)
                return
            
            # Reset the flag when hotkey is pressed (new session)
            _initial_message_spoken = False
            _last_message_time = 0  # Reset time as well
            
            keep_listening = True
            while keep_listening and not should_exit_program:
                keep_listening = wait_for_wake_word_and_start()
                # After returning from a conversation, reset the flag so we don't speak again
                # unless the user presses the hotkey again
                if not keep_listening:
                    _initial_message_spoken = False
        except Exception as e:
            print(f"Error while handling wake word workflow: {e}")
        finally:
            handler.reset_running_state()
            # Reset flag when done
            _initial_message_spoken = False
            _last_message_time = 0
    
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
        global stop_monitoring, should_exit_program, flask_server, flask_thread
        stop_monitoring.set()
        should_exit_program = True
        stop_current_mode()
        if flask_server:
            print("Shutting down Flask server...")
            try:
                flask_server.shutdown()
                flask_server.server_close()
            except Exception as e:
                print(f"Error shutting down Flask server: {e}")
        if flask_thread and flask_thread.is_alive():
            flask_thread.join(timeout=5)
        print("Shutdown complete. Goodbye!")
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    main(hotkey=args.hotkey_combo, skip_wake_word=args.skip_wake_word)