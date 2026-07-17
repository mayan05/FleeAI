# FleeAI ✈️

**FleeAI** is a multi-agent AI system that automates flight booking through natural conversation. Instead of clicking through filters and forms, users describe what they want in plain English — FleeAI's three collaborating agents understand the request, search and rank flight options, and walk the user through confirming a booking.

Built with **CrewAI**, **Streamlit**, **Ollama** (local LLM), and **Duffel** (flight API sandbox) — runs entirely on your machine with zero cloud LLM costs.

---

## Architecture

Three CrewAI agents, each with a single responsibility, coordinated by a Python orchestrator (`src/orchestrator.py`) that acts as a state machine:

```
User message
     │
     ▼
┌─────────────────────────┐
│ Agent 1: Query           │  extracts FlightQuery from natural language
│ Understanding            │  → asks a clarification question if origin /
│ (src/agents/query_agent) │    destination / date is missing, instead of
└─────────────────────────┘    guessing
     │  FlightQuery (is_complete=True)
     ▼
┌─────────────────────────┐
│ Deterministic Python     │  resolve_relative_date(): "next Friday" → real
│ resolution (no LLM)      │  YYYY-MM-DD date (also handles explicit dates
│ - date_resolver.py       │  like "2026-07-16", "July 20", "16 Jul 2026")
│ - iata_lookup.py         │  city_to_iata(): "Bangalore" → "BLR"
└─────────────────────────┘  (unrecognized city/date ⇒ ask user, never guess)
     │  FlightQuery (IATA-resolved)
     ▼
┌─────────────────────────┐
│ Agent 2: Flight Search &  │  calls Duffel /air/offer_requests, filters by
│ Ranking                  │  budget_inr, sorts by price, attaches a
│ (src/agents/search_agent)│  rank_reason to each option
└─────────────────────────┘
     │  RankedFlights (or empty options + summary)
     ▼
   User selects an option (by number) in the Streamlit UI
     │  FlightOption
     ▼
┌─────────────────────────┐
│ Agent 3: Booking &        │  calls the booking tool directly from Python
│ Confirmation              │  (no LLM round-trip) — generates PNR, computes
│ (src/agents/booking_agent)│  total price, builds itinerary summary
└─────────────────────────┘
     │  BookingConfirmation
     ▼
Streamlit renders the final confirmation card
```

**Key design decisions:**

- **Fully local inference.** All LLM calls run through Ollama (`llama3.2:3b`) on your machine — no cloud API keys needed for the model, no rate limits, no cost. The model and prompts are optimized for fast, reliable structured extraction on CPU.
- **Data contracts, not free text.** Every agent's input/output is a validated Pydantic model (`src/schemas/models.py`: `FlightQuery`, `FlightOption`, `RankedFlights`, `BookingConfirmation`, `OrchestratorResponse`). This guarantees each agent's output is parseable by the next, and by the UI.
- **The LLM never does arithmetic or lookups it's unreliable at.** Relative dates ("next Friday") and city→IATA-code resolution happen in plain, deterministic Python — not inside a prompt — because LLMs are known to get weekday math and obscure airport codes wrong.
- **Agents never invent flight/booking data.** Every numeric or ID field (price, duration, stops, PNR) comes directly from a tool call to Duffel or the simulated booking tool. The LLM's only creative contribution is `rank_reason` and `itinerary_summary`.
- **Booking bypasses the LLM entirely.** Agent 3's booking tool is pure deterministic Python (PNR generation, price math). Rather than routing it through a slow local model, `run_booking()` calls the tool function directly — making booking instant and eliminating LLM output parsing failures.
- **The orchestrator is a single state machine (`FleeAISession`)**, so the Streamlit UI never has to know agent internals — it just calls `.start()` / `.respond()` and renders whatever `OrchestratorResponse.stage` tells it to.

---

## Getting Started

### Prerequisites
- Python 3.11
- [`uv`](https://github.com/astral-sh/uv) (package manager)
- [Ollama](https://ollama.com/) installed and running locally
- A free [Duffel Developer account](https://app.duffel.com/) in **Test Mode**, for a `duffel_test_...` token

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/mayan05/FleeAI.git
cd FleeAI

# 2. Sync the environment from pyproject.toml / uv.lock
uv sync

# 3. Pull the Ollama model
ollama pull llama3.2:3b

# 4. Add your API keys
cp .env.example .env
# Edit .env and fill in DUFFEL_ACCESS_TOKEN with your own key
```

### Run the app

You can run the app locally using Python, or spin everything up at once using Docker.

**Option A: Docker Compose (One-command setup)**
```bash
# Starts both the Ollama server and the Streamlit app together.
# It automatically uses the llama3.2:3b model downloaded to your host machine.
docker-compose up --build
```
Opens at **http://localhost:8501** — type a flight request and go.

**Option B: Manual Python setup**
```bash
# 1. Make sure Ollama is running on your machine
ollama serve

# 2. Start the Streamlit app
uv run streamlit run src/app.py
```
Opens at **http://localhost:8501** — type a flight request and go.

### Run the tests

```bash
# Run pytest for unit/auth tests
PYTHONPATH=. uv run pytest

# Run individual agent end-to-end test scripts
uv run python -m tests.test_day1_agent1
uv run python -m tests.test_day2_agent2
uv run python -m tests.test_day3_agent3
```

---

## LLM Configuration

All agents share a single LLM config at `src/llm_config.py`. The current setup uses **Ollama** with `llama3.2:3b` for local inference:

```python
fleeai_llm = LLM(
    model="ollama/llama3.2:3b",
    base_url="http://localhost:11434",
    temperature=0.1,
)
```

**Switching models:** To use a different Ollama model, just change the `model` string (e.g. `"ollama/llama3.1:8b"` for better accuracy but slower speed). To switch back to a cloud provider like Groq, change to `model="groq/llama-3.3-70b-versatile"` and add your `GROQ_API_KEY` to `.env`.

---

## Known Limitations

- **Local model speed.** The 3B model on CPU takes ~30-90 seconds per agent call. A GPU-accelerated setup or a larger model (8B+) on GPU will be significantly faster.
- **Duffel sandbox data is not real.** In Test Mode, Duffel returns simulated prices and schedules from its own mock airline ("Duffel Airways") rather than live fares — this is expected sandbox behavior, not a bug in our code. Real prices would require an activated (production) Duffel account.
- **IATA coverage is a static list.** `src/utils/iata_lookup.py` maps ~35 major Indian cities to IATA codes. A city outside this list triggers a clarification question asking for the 3-letter code directly, rather than failing silently.
- **No real payment/order flow.** Agent 3 simulates booking (PNR generation, price totalling, status) instead of calling Duffel's live order/payment endpoint, which needs a funded account and real card details.
- **Session state is in-memory only.** Refreshing the browser tab loses the current conversation; there's no persistent chat history or user accounts.
- **Clarification loop caps at 5 rounds** (`MAX_CLARIFICATION_ROUNDS` in `orchestrator.py`) before asking the user to rephrase their whole request, to avoid an infinite back-and-forth if Agent 1 can't converge.
- **Single currency (INR), one-way search only.** `FlightQuery.return_date` exists in the schema but round-trip search isn't wired into Agent 2 yet.

---

## Edge Cases Handled

| Scenario | Behavior |
|---|---|
| No flights found for route/date | Agent 2 returns an empty `options` list with a clear `summary`; UI shows the message and resets for a new search |
| Budget too low for any result | Same empty-options path, with a summary explicitly naming the budget cap |
| Unrecognized/ambiguous city name | Orchestrator catches the failed IATA lookup and asks the user for the 3-letter airport code directly |
| Explicit date in wrong field | `date_resolver.py` handles ISO dates (`2026-07-16`), month names (`July 20`, `16 Jul`), and `MM/DD/YYYY` formats as fallback |
| Unparseable relative date phrase | `date_resolver.py` returns `None`; orchestrator re-flags the query incomplete and asks for an exact date |
| User changes their mind mid-flow | Typing `restart`, `cancel`, `reset`, or `new search` at any point (mid-clarification or mid-selection) wipes the session and starts fresh |
| Invalid flight selection (bad number) | Orchestrator re-prompts with the valid range instead of crashing |
| Agent 1/2/3 exception (network error, malformed LLM output) | Caught in the orchestrator, surfaced as a friendly `error` stage message, session auto-resets |

---

## Team

- **Mayan** — repo/environment setup, shared schemas, LLM config (Groq → Ollama migration), Agent 1 (Query Understanding), orchestrator + Streamlit UI shell
- **Shashank** — Duffel API integration, Agent 2 (Flight Search & Ranking), Agent 3 (Booking & Confirmation), edge-case hardening