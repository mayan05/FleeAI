# FleeAI ✈️

**FleeAI** is a multi-agent AI system that automates flight booking through natural conversation. Instead of clicking through filters and forms, users describe what they want in plain English — FleeAI's three collaborating agents understand the request, search and rank flight options, and walk the user through confirming a booking.

Built with **CrewAI**, **Streamlit**, and free-tier APIs (Groq LLM + Duffel sandbox) — no paid infrastructure required to run or demo.

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
│ resolution (no LLM)      │  YYYY-MM-DD date
│ - date_resolver.py       │  city_to_iata(): "Bangalore" → "BLR"
│ - iata_lookup.py         │  (unrecognized city/date ⇒ ask user, never guess)
└─────────────────────────┘
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
│ Agent 3: Booking &        │  compiles a simulated booking order (PNR,
│ Confirmation              │  total price, status) deterministically, and
│ (src/agents/booking_agent)│  writes a friendly itinerary_summary
└─────────────────────────┘
     │  BookingConfirmation
     ▼
Streamlit renders the final confirmation card
```

**Key design decisions:**

- **Data contracts, not free text.** Every agent's input/output is a validated Pydantic model (`src/schemas/models.py`: `FlightQuery`, `FlightOption`, `RankedFlights`, `BookingConfirmation`, `OrchestratorResponse`). This guarantees each agent's output is parseable by the next, and by the UI.
- **The LLM never does arithmetic or lookups it's unreliable at.** Relative dates ("next Friday") and city→IATA-code resolution happen in plain, deterministic Python — not inside a prompt — because LLMs are known to get weekday math and obscure airport codes wrong.
- **Agents never invent flight/booking data.** Every numeric or ID field (price, duration, stops, PNR) comes directly from a tool call to Duffel or the simulated booking tool. The LLM's only creative contribution is `rank_reason` and `itinerary_summary`.
- **The orchestrator is a single state machine (`FleeAISession`)**, so the Streamlit UI never has to know agent internals — it just calls `.start()` / `.respond()` and renders whatever `OrchestratorResponse.stage` tells it to.

---

## Getting Started

### Prerequisites
- Python 3.11
- [`uv`](https://github.com/astral-sh/uv) (package manager)
- A free [Groq API key](https://console.groq.com/keys)
- A free [Duffel Developer account](https://app.duffel.com/) in **Test Mode**, for a `duffel_test_...` token

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-org/FleeAI.git
cd FleeAI

# 2. Sync the environment from pyproject.toml / uv.lock
uv sync

# 3. Add your API keys
cp .env.example .env
# Edit .env and fill in GROQ_API_KEY and DUFFEL_ACCESS_TOKEN with your own keys
```

> ⚠️ **Rotate the keys in `.env.example` before your next push.** `.env.example` is *not* gitignored (only `.env` is), and the current committed `.env.example` contains what look like real, live values instead of placeholders. Anyone who clones the repo can read them off GitHub right now. Revoke/regenerate both the Groq key and the Duffel test token, then replace the file's contents with placeholder text (e.g. `GROQ_API_KEY=your_key_here`) before your final push.

### Run the app

```bash
uv run streamlit run src/app.py
```

Opens at **http://localhost:8501** — type a flight request and go.

### Run the standalone agent tests

```bash
uv run python -m tests.test_day1_agent1
uv run python -m tests.test_day2_agent2
uv run python -m tests.test_day3_agent3
```

---

## Known Limitations

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
| Unparseable relative date phrase | `date_resolver.py` returns `None`; orchestrator re-flags the query incomplete and asks for an exact date |
| User changes their mind mid-flow | Typing `restart`, `cancel`, `reset`, or `new search` at any point (mid-clarification or mid-selection) wipes the session and starts fresh |
| Invalid flight selection (bad number) | Orchestrator re-prompts with the valid range instead of crashing |
| Agent 1/2/3 exception (bad API key, network error, malformed LLM output) | Caught in the orchestrator, surfaced as a friendly `error` stage message, session auto-resets |

---

## Team

- **Mayan** — repo/environment setup, shared schemas, LLM config, Agent 1 (Query Understanding), orchestrator + Streamlit UI shell
- **Shashank** — Duffel API integration, Agent 2 (Flight Search & Ranking), Agent 3 (Booking & Confirmation), edge-case hardening