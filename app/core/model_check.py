from google import genai
from app.core.config import get_settings

client = genai.Client(api_key=get_settings().gemini_api_key)

# List all models supporting generateContent
for model in client.models.list():
    if "generateContent" in model.supported_actions:
        print(model.name)