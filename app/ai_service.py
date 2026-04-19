import os
import json
from google import genai
from google.genai import types

from .models import CommandSchema

# Ensure API key is configured
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Log a warning; the app will still start but AI calls will fail until set.
    import logging
    logging.warning("GEMINI_API_KEY is not set. Please set it in your environment or .env file.")

from dotenv import load_dotenv

# Lazy initialization function
def get_client():
    # Force reload of .env so it picks up the key even if Uvicorn didn't restart
    load_dotenv(override=True)
    current_key = os.getenv("GEMINI_API_KEY")
    
    if not current_key or current_key.strip() == "":
        return genai.Client(api_key="dummy_key_for_tests")
        
    return genai.Client(api_key=current_key.strip())

SYSTEM_PROMPT = """
You are a backend CLI and API parser assistant. Your job is to take a natural language instruction from a user and convert it into a structured command schema.

# Rules:
1. Always return valid JSON. Do NOT wrap it in Markdown like ```json ... ```. Just return raw JSON. 
2. If the user request is destructive (e.g., delete everything, drop a table, wipe the server), set `is_safe` to false. For regular read, minor fix, or safe create ops, set `is_safe` to true.
3. If the user request does not contain enough context to safely or accurately deduce the backend operation, set `needs_clarification` to true and provide a `clarification_message`.
4. The `op` (operation name) should be namespaced like `module.action` (e.g. `system.check_and_fix`, `user.create`, `database.backup`).
"""

def parse_instruction_to_command(instruction: str) -> CommandSchema:
    """
    Sends the user's natural language instruction to Gemini and parses 
    the result into our structured CommandSchema.
    """
    try:
        client = get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"User instruction: {instruction}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=CommandSchema,
                temperature=0.0
            ),
        )
        
        # Parse the text response into our Pydantic model
        # Using Google GenAI SDK, if response_schema is provided, it returns text that conforms to the schema.
        result_json = response.text
        
        # Strip potential markdown formatting
        result_json = result_json.strip()
        if result_json.startswith("```json"):
            result_json = result_json[7:]
        elif result_json.startswith("```"):
            result_json = result_json[3:]
        if result_json.endswith("```"):
            result_json = result_json[:-3]
        result_json = result_json.strip()
        
        return CommandSchema.model_validate_json(result_json)
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(trace) # Still print to console
        # Throw the full traceback out so we can see it on the React frontend!
        raise RuntimeError(f"{str(e)}\n\nTraceback:\n{trace}")
