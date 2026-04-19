<div align="center">
  <img src="frontend/src/assets/hero.png" width="80px" alt="Logo"/>
  <h1>AI Command Parser Engine</h1>
  <p>A production-ready NLP-to-Command layer prioritizing security, scale, and performance.</p>
</div>

## 🚀 Overview
The **AI Command Parser Engine** takes raw natural language instructions from users and translates them into structured, actionable JSON payloads for backend execution. 

Designed with a **security-first startup mindset**, this architecture ensures destructive AI outputs are caught before causing execution damage, allowing developers to integrate LLMs into live backend logic safely.

---

## 🔥 Key Engineering Highlights
* **Zero-Trust Validation:** Hardcoded backend whitelist strictly blocks destructive AI outputs (e.g. data drops).
* **Startup Pragmatism:** Prioritizes absolute system safety over micro-latency raw execution speed.
* **Isolated Infrastructure:** Stateless, decoupled frontend and backend guarantees horizontal scalability.
* **Strict Payload schemas:** Uses Pydantic to ensure all generated JSON natively conforms without crashes.
* **Cost-Optimized Cloud:** Native support for Vercel/Render, achieving production scale with zero overhead.

---

## 🛠️ Tech Stack
* **Frontend:** React + Vite, customized with a premium Glassmorphism UI
* **Backend:** Python + FastAPI for rapid, asynchronous microservice execution
* **AI Provider:** Google Gemini API (2.5 Flash) via `google-genai` SDK
* **Validation:** Pydantic models for strict structured data enforcement

---

## 💻 Local Development

### 1. Setup the Backend (FastAPI)
```bash
# Install dependencies
pip install -r requirements.txt

# Create a .env file and add your Google API Key
echo 'GEMINI_API_KEY="your-api-key-here"' > .env

# Run the server
uvicorn app.main:app --reload --port 8000
```
*The backend will boot up at `http://localhost:8000`*

### 2. Setup the Frontend (Vite)
```bash
cd frontend

# Install dependencies
npm install

# Run the React environment
npm run dev
```
*The beautiful UI will open at `http://localhost:5173`*

---

## 🔒 Security Architecture
Relying purely on LLM models to control live backend logic is a security vulnerability. This system solves that through a Dual-Layer Validation process:
1. **AI Output Sanity Check:** The LLM internally attempts to classify if the prompt is safe or `destructive`.
2. **Backend Policy Check:** Irrespective of the AI's internal flag, the request is passed through a Pydantic `CommandSchema` against `security_policy.py`. Validations against `ALLOWED_OPERATIONS` protect against prompt injection or logic hallucination.

---

## ☁️ Deployment (Free Tier)
This codebase is natively optimized to be deployed 100% free with the following providers:
* **Backend**: Render.com (Web Service) using `Python 3.11.8`.
* **Frontend**: Vercel by mapping `VITE_API_URL` to your active Render web service.

*Note: Ensure you include your Environment variables (`GEMINI_API_KEY`, `APP_SECRET_KEY`) on Render to authorize remote UI connections.*
