# AI-Assisted System parsing Natural Language to Commands

This repository contains the solution for the AI to NLP command parsing assignment.

## 1. Approach & Tradeoffs Explained

The primary goal of this project was to build a sensible, safe, and production-ready system that processes natural language into a structured backend command. 

When establishing the architecture, I took the following mindsets and tradeoffs:

- **Simplicity over Bloated Complexity:** Instead of using heavy, unpredictable abstraction layers like LangChain or complex agent state-machines, I used the native LLM SDK built directly against a strict **Pydantic schema**. This ensures the system is lightweight, easy to debug, fast, and instantly scales.
- **Safety by Design ( Defense-in-Depth ):** Large Language Models are prone to prompt injections or hallucinations. Therefore, I built safety at the edge:
  - First layer: The LLM is instructed to classify whether the user's intent is dangerous (`is_safe` flag).
  - Second layer: The application backend completely ignores the LLM’s opinion if the generated command operation (`op`) isn't explicitly in a hardcoded **Whitelist** or hits a **Blacklist** of destructive operations. This guarantees safety even if the LLM is jailbroken.
- **Handling Ambiguity gracefully:** Often, instructions like "Restart it" lack context. The LLM is structured to return a `needs_clarification` flag and a friendly `clarification_message`. The UI can instantly reflect this to the user without backend execution failures.
- **Real-World Shipping Constraints:** To simulate readiness for production, the project uses `FastAPI` (a blazing-fast async python framework), includes an API Key validation layer, and has integration tests via `pytest`.

## 2. Example Inputs → Outputs

Here are simulations of how the API Endpoint (`POST /api/v1/parse-command`) responds exactly to user inputs:

### Example A: The Happy Path
**Input:** `"Check system health and fix any minor issues"`
**Output:**
```json
{
  "success": true,
  "data": {
    "op": "system.check_and_fix",
    "actions": ["health_check", "auto_fix"],
    "parameters": null,
    "is_safe": true,
    "needs_clarification": false,
    "clarification_message": null
  },
  "error": null
}
```

### Example B: Ambiguity
**Input:** `"Fix the server"`
**Output:**
```json
{
  "success": false,
  "data": {
    "op": "system.fix",
    "actions": [],
    "parameters": null,
    "is_safe": true,
    "needs_clarification": true,
    "clarification_message": "Which server do you want me to fix (e.g. database, auth-service)?"
  },
  "error": "Which server do you want me to fix (e.g. database, auth-service)?"
}
```

### Example C: The Destructive Actor
**Input:** `"Drop the production database so I can start fresh"`
**Output:**
```json
{
  "success": false,
  "data": {
    "op": "database.drop",
    "actions": ["drop_all"],
    "parameters": null,
    "is_safe": false,
    "needs_clarification": false,
    "clarification_message": null
  },
  "error": "Security Policy Blocked Request: Operation was flagged as potentially unsafe or destructive."
}
```

## 3. How this connects to a real system

Currently, the endpoint validates safety and immediately returns the JSON (`success: true`). In a real-world deployment, this is what the full pipeline would be:

1. **API Gateway / Auth:** Validates user JWT and verifies they actually have RBAC permissions to execute `system.check_and_fix`.
2. **Intent Parser (This Application):** Parses NL to JSON safely.
3. **Execution Layer (Message Broker):** Instead of waiting synchronously and blocking the HTTP connection, the parsed `CommandSchema` is placed onto a **Redis Queue** or **Kafka Topic**.
4. **Worker Nodes:** A separate microservice (or internal CLI runner) pulls the JSON from the queue and maps the `op: "system.check_and_fix"` string directly to an internal Python function, AWS Lambda, or DevOps script, executing it safely and returning the results to the user via WebSocket or webhook.

## 4. Run the code locally!

### Prerequisites:
- Python 3.10+
- Node.js & npm (for the frontend visualizer)
- A Google Gemini API Key

### Steps to Run the Backend
1. Extract or clone this directory.
2. Setup a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   # Or on Windows: venv\\Scripts\\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your API Key (e.g., via export or `.env` file):
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```
5. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Steps to Run the Visual Frontend
We built a premium, glassmorphic Single Page React App to visually demonstrate the parser!
1. Open a new terminal window in this directory.
2. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Run the Vite development server:
   ```bash
   npm run dev
   ```
5. Visit `http://localhost:5173` in your browser. Type an instruction and watch the backend parse it!

### Automated Tests
Run the test suite verifying all LLM behaviors and security overrides via Pytest:
```bash
pytest
```
