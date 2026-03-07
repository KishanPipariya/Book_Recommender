import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("GOOGLE_API_KEY not found in .env")
else:
    client = genai.Client(api_key=api_key)
    print("Available models:")
    for model in client.models.list():
        print(f"Name: {model.name}, Supported Methods: {model.supported_actions}")
