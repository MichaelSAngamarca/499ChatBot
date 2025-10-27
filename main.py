import os
import signal
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from tools import client_tools
from connectivity_checker import check_internet_connectivity, safe_api_call
from offline_mode import OfflineMode

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

def run_online_mode(conversation):
    """Run the online conversation mode."""
    try:
        conversation.start_session()
        signal.signal(signal.SIGINT, lambda sig, frame: conversation.end_session())
        conversation_id = conversation.wait_for_session_end()
        print(f"Conversation ID: {conversation_id}")
        return True
    except Exception as e:
        print(f"Error during online conversation: {e}")
        return False

def main():
    """Main function that handles online/offline mode switching."""
    print("="*60)
    print("TalkAssist - Starting Application")
    print("="*60)
    
    print("Checking internet connectivity...")
    if not check_internet_connectivity():
        print("No internet connection detected. Starting offline mode...")
        offline_mode = OfflineMode()
        offline_mode.run()
        return
    
    print("Internet connection detected. Attempting to start online mode...")
    
    conversation = initialize_online_mode()
    
    if conversation is None:
        print("Failed to initialize online mode. Falling back to offline mode...")
        offline_mode = OfflineMode()
        offline_mode.run()
        return
    
    print("Starting online conversation...")
    success = run_online_mode(conversation)
    
    if not success:
        print("Online mode failed. Falling back to offline mode...")
        offline_mode = OfflineMode()
        offline_mode.run()

if __name__ == "__main__":
    main()