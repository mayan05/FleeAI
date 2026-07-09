# FleeAI ✈️

**FleeAI** is a multi-agent AI system that automates flight booking through natural conversation. Instead of clicking through filters and forms, users describe what they want in plain English — FleeAI's three collaborating agents understand the request, search and rank real flight options, and walk the user through confirming a booking.

Built with **CrewAI**, **Python**, and free-tier LLM/flight-data APIs (Groq + Amadeus self-service sandbox) — no paid infrastructure required to run or demo.

### Repo description (GitHub "About" field, one-liner)
> Multi-agent AI flight booking assistant built with CrewAI — understands natural language requests, searches & ranks flights, and handles booking confirmation, powered by 3 specialized agents.

---

## Architecture

Three CrewAI agents, each with a single responsibility, coordinated by a sequential Crew process:

1. **Query Understanding Agent** — parses natural language into structured flight search parameters (origin, destination, dates, budget, preferences), and flags what's missing so the system can ask a follow-up instead of guessing.
2. **Flight Search & Ranking Agent** — queries the flight data API, filters/ranks results against the user's stated preferences, and explains *why* each option is recommended.
3. **Booking & Confirmation Agent** — confirms the selected flight back to the user, simulates the booking, and produces a final itinerary summary.

Data is passed between agents as validated Pydantic objects (see `src/schemas/`), so each agent's output is guaranteed to be parseable by the next.

## Team
- **Mayan** — Query Understanding Agent, orchestration, schemas
- **Shashank** — Flight Search/Ranking Agent, Booking Agent, API integration

## Status
🚧 Day 1 of 4 — project scaffold + Agent 1 (Query Understanding) in progress.