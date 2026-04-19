from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class CommandRequest(BaseModel):
    instruction: str = Field(..., description="The natural language instruction from the user.")

class CommandSchema(BaseModel):
    op: str = Field(..., description="The structured operation name (e.g., 'system.check_and_fix', 'user.create').")
    actions: List[str] = Field(default_factory=list, description="A list of specific actions required to execute the operation.")
    parameters: dict = Field(default_factory=dict, description="Payload or arguments needed for the operation. Leave as empty object {} if none.")
    
    # Safety and Ambiguity Fields
    is_safe: bool = Field(..., description="Boolean flag. Must be True if the operation is completely safe. Must be False if it is destructive (e.g., dropping databases, deleting data) or potentially harmful.")
    needs_clarification: bool = Field(..., description="Boolean flag to indicate if the user's instruction is too vague and needs clarification before converting to a command.")
    clarification_message: str = Field(default="", description="If needs_clarification is True, provide a message asking the user for the missing details. Otherwise return an empty string ''.")

class CommandResponse(BaseModel):
    success: bool
    data: Optional[CommandSchema] = None
    error: Optional[str] = None
