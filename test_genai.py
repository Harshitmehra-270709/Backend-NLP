import os
import traceback
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")

print(f"API Key loaded. Length: {len(api_key) if api_key else 'None'}")
if api_key and "\r" in api_key:
    print("WARNING: API key has carriage returns!")

from pydantic import BaseModel, Field
from typing import List, Dict, Any

class CommandSchema(BaseModel):
    op: str = Field(..., description="The structured operation name (e.g., 'system.check_and_fix', 'user.create').")
    actions: List[str] = Field(default_factory=list, description="A list of specific actions required to execute the operation.")
    parameters: dict = Field(default_factory=dict, description="Payload.")
    is_safe: bool = Field(...)
    needs_clarification: bool = Field(...)
    clarification_message: str = Field(default="")

try:
    client = genai.Client(api_key=api_key.strip() if api_key else "dummy_key")
    
    SYSTEM_PROMPT = "You are a parser. Parse hello world."
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Hello world",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CommandSchema,
            temperature=0.0
        ),
    )
    print("SUCCESS: ", response.text)
except Exception as e:
    print("ERROR CAUGHT:")
    traceback.print_exc()
