Perfect — here’s the assignment.

I want to see how you approach a real-world problem aligned with what we’re building.

### Objective:
Design a simple AI-assisted system that can take a natural language instruction and convert it into a structured command that could be executed by a backend system.

### Example:
Input:
“Check system health and fix any minor issues”

Output:
{
 "op": "system.check_and_fix",
 "actions": ["health_check", "auto_fix"]
}

---

### Your task:
1. Define a command schema (JSON structure) for handling different types of instructions 
2. Build a simple pipeline (can be conceptual or code) that:
 - takes natural language input
 - parses it into structured commands
3. Show how you would handle:
 - ambiguity
 - unsafe or destructive requests
4. Bonus:
 - suggest how this could connect to a real system (API, database, etc.)

---

### Deliverable:
- Short explanation (how you approached it)
- Example inputs → outputs
- Optional: working code or pseudocode

Keep it simple and practical — I care more about how you think than complexity.

Take your time and send it when ready.