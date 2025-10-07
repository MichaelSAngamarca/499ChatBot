from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from langchain_community.tools import DuckDuckGoSearchRun

def searchWeb(parameters):
    query = parameters.get("query")
    if not query:
        return "No query provided."
    search = DuckDuckGoSearchRun()
    results = search.run(query)
    return results
def save_to_txt(parameters):
    filename = parameters.get("filename")
    data = parameters.get("data")
    
    formatted_data = f"{data}"
    
    with open(filename, "a", encoding="utf-8") as file:
        file.write(formatted_data + "\n")
client_tools = ClientTools()
client_tools.register("searchWeb",searchWeb)
client_tools.register("saveToTxt",save_to_txt)