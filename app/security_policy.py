import logging

# Set up simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A simple whitelist of system operations that are permitted.
# In a real app, this might be tied to specific user roles or fetched from DB.
ALLOWED_OPERATIONS = {
    "system.check_and_fix",
    "system.health_check",
    "user.create",
    "user.update",
    "service.restart"
}

# Operations that are outright denied to showcase safety rails
DANGEROUS_OPERATIONS = {
    "database.drop",
    "system.rm_rf",
    "user.delete_all"
}

def validate_command_safety(op: str, is_safe_flag: bool) -> tuple[bool, str]:
    """
    Validates if the translated command is safe to execute based on 
    the system's rules and the LLM's assessment.
    Returns (is_valid: bool, reason: str)
    """
    # 1. Check if the LLM flagged it as unsafe
    if not is_safe_flag:
        logger.warning(f"Operation '{op}' was flagged as unsafe by the AI.")
        return False, "Operation was flagged as potentially unsafe or destructive."

    # 2. Check if the op is in an explicitly blocked list
    if op in DANGEROUS_OPERATIONS:
        logger.warning(f"Blocked explicit dangerous operation: {op}")
        return False, "Operation is explicitly blocked by security policy."

    # 3. Check if the op is whitelisted (default deny approach)
    if op not in ALLOWED_OPERATIONS:
        logger.warning(f"Operation '{op}' is not in the allowed list.")
        return False, f"Operation '{op}' is not permitted. Allowed ops: {', '.join(ALLOWED_OPERATIONS)}"

    return True, "Operation is safe and whitelisted."
