import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

from app.models import CommandRequest, CommandResponse
from app.ai_service import parse_instruction_to_command
from app.security_policy import validate_command_safety

app = FastAPI(
    title="AI Command Parser API",
    description="An API to convert natural language instructions into structured backend commands securely.",
    version="1.0.0"
)

# Enable CORS for all origins since we don't know the Vercel URL yet
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Very basic security mechanism (simulating an API key for actual endpoint use)
# In production, this would use OAuth2, JWTs, or robust API Gateway features.
def verify_api_key(x_api_key: str = Header(None)):
    expected_key = os.getenv("APP_SECRET_KEY", "dev-secret-key-123")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return x_api_key

@app.post("/api/v1/parse-command", response_model=CommandResponse)
async def parse_command(request: CommandRequest, api_key: str = Depends(verify_api_key)):
    """
    Takes a natural language instruction, converts it via AI to a structured command,
    and applies security validations before returning it to the caller.
    """
    if not request.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty.")

    try:
        # Step 1: Pass to AI layer
        parsed_command = parse_instruction_to_command(request.instruction)
        
        # Step 2: Handle ambiguity
        if parsed_command.needs_clarification:
            return CommandResponse(
                success=False,
                error=parsed_command.clarification_message,
                data=parsed_command
            )
            
        # Step 3: Run security & safety policies
        is_safe, reason = validate_command_safety(parsed_command.op, parsed_command.is_safe)
        
        if not is_safe:
            return CommandResponse(
                success=False,
                error=f"Security Policy Blocked Request: {reason}",
                data=parsed_command
            )
            
        # Step 4: All checks passed - ready to execute
        # (In a real system, we might push this to a Redis queue or an execution engine here)
        return CommandResponse(
            success=True,
            data=parsed_command
        )
        
    except Exception as e:
        # Log unexpected errors here out of band
        import traceback
        trace = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\n{trace}")

@app.get("/health")
async def health_check():
    """Simple status check."""
    return {"status": "ok"}
