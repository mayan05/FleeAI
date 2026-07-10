# FleeAI ✈️

**FleeAI** is a multi-agent AI system that automates flight booking through natural conversation. Instead of clicking through filters and forms, users describe what they want in plain English — FleeAI's three collaborating agents understand the request, search and rank real flight options, and walk the user through confirming a booking.

Built with **CrewAI**, **Python**, and free-tier APIs (Groq LLM + Duffel sandbox) — no paid infrastructure required to run or demo.

---

## Architecture

Three CrewAI agents, each with a single responsibility, coordinated by a sequential Crew process:

1. **Query Understanding Agent** — parses natural language into structured flight search parameters (origin, destination, dates, budget, preferences), and flags what's missing so the system can ask a follow-up instead of guessing.
2. **Flight Search & Ranking Agent** — calls the Duffel API, filters/ranks results against the user's stated preferences, and explains *why* each option is recommended.
3. **Booking & Confirmation Agent** — confirms the selected flight back to the user, simulates the booking via Duffel sandbox, and produces a final itinerary summary.

Data is passed between agents as validated Pydantic objects (see `src/schemas/`), so each agent's output is guaranteed to be parseable by the next.

---

## Getting Started

### Prerequisites
- Python 3.11
- [`uv`](https://github.com/astral-sh/uv) (package manager)
- A free [Groq API key](https://console.groq.com/keys)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-org/FleeAI.git
cd FleeAI

# 2. Create and activate the virtual environment
uv venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Edit .env and fill in your GROQ_API_KEY
```

### Run the app

```bash
streamlit run src/app.py
```

Opens at **http://localhost:8501** — just type a flight request and go.