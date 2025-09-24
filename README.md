To Run The Demo.

First you need to install everything in the reqiurments.txt file which includes:
elevenlabs
pyaudio
openai
dotenv
pillow
langchain_community

You can do a simple install by doing the command uv pip install -r requirments.txt. if this does not work then you can simply manually install by doing pip  install then the package name. 

Id recomended you setup the virtual enviroment by simply doing python -m venv venv which sets up a local virtual enviroment. 

Once you pull this repo you can then simply run the main.py file by doing python .\main.py to run the program. It should then start the chatbot and you should hear the chatbot speak. it already by default has microphone access due to pyaudio so permissions as of right now are set to alwasys on by defualt. 

You can ask it some questons but as of rigt now does not do much. To end the conversation simply say something that mentions that you want to end the converstaion and it should do it automatically. 
