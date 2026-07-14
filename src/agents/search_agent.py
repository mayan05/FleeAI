import os
import re
import requests
from crewai import Agent, Crew, Task
from crewai.tools import tool
from src.llm_config import fleeai_llm
from src.schemas.models import FlightQuery, FlightOption, RankedFlights

def _parse_iso8601_duration_minutes(duration: str | None) -> int:
    """Parses a Duffel-style ISO 8601 duration (e.g. 'PT10H35M') into minutes.
    Falls back to 0 if duration is missing or unparseable, rather than
    raising -- a missing duration shouldn't crash the whole search.
    """
    if not duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes

@tool("Search and Filter Duffel Flights")
def search_duffel_flights(origin: str, destination: str, departure_date: str, preferences: str, budget_inr: str = "0") -> dict:
    """Searches Duffel API for flights and filters them by budget and preferences.
    Pass budget_inr as a numeric string (e.g. '5000'). Pass '0' if there is no budget constraint.
    """
    access_token = os.environ.get("DUFFEL_ACCESS_TOKEN")
    if not access_token:
        return {"summary": "Error: DUFFEL_ACCESS_TOKEN is not set.", "options": []}

    try:
        url = "https://api.duffel.com/air/offer_requests"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Duffel-Version": "v2",
            "Content-Type": "application/json"
        }
        payload = {
            "data": {
                "slices": [{
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date
                }],
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy"
            }
        }

        # Bypass the SDK and call the Duffel API directly using standard requests
        response_raw = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            params={"return_offers": "true"}
        )
        
        if response_raw.status_code != 201:
            return {"summary": f"API Error: {response_raw.text}", "options": []}

        response_data = response_raw.json().get("data", {})
        offers = response_data.get("offers", [])
        
        if not offers:
            return {"summary": "No flights found for this route and date.", "options": []}

        # Deterministic Python logic: Filter by budget.
        # budget_inr arrives as a string (avoids Groq nullable-float schema issues).
        # Values like 'null', 'none', '', '0' all mean no cap.
        _raw = str(budget_inr).strip().lower()
        try:
            budget_float = float(_raw) if _raw not in ("", "null", "none", "0") else 0.0
        except ValueError:
            budget_float = 0.0
        effective_budget = float("inf") if budget_float <= 0 else budget_float

        valid_options = []
        for offer in offers:
            price = float(offer["total_amount"])
            if price <= effective_budget:
                flight_slice = offer["slices"][0]
                segments = flight_slice["segments"]
                first_segment = segments[0]
                last_segment = segments[-1]

                valid_options.append({
                    "flight_id": offer["id"],
                    "airline": first_segment["operating_carrier"]["name"],
                    "origin": flight_slice["origin"]["iata_code"],
                    "destination": flight_slice["destination"]["iata_code"],
                    "departure_time": first_segment["departing_at"],
                    "arrival_time": last_segment["arriving_at"],
                    "stops": len(segments) - 1,
                    "duration_minutes": _parse_iso8601_duration_minutes(flight_slice.get("duration")),
                    "price_inr": round(price),
                })

        if not valid_options:
            cap_msg = f"under the budget of ₹{int(budget_float):,} INR" if budget_float > 0 else "for this route and date"
            return {"summary": f"Flights found, but none {cap_msg}.", "options": []}

        # Deterministic Python logic: Sort by price (cheapest first)
        valid_options.sort(key=lambda x: x["price_inr"])

        # FIX: Limit to the top 5 results to prevent token limit errors
        top_options = valid_options[:5]

        return {
            "summary": f"Found {len(valid_options)} flights matching criteria. Showing top {len(top_options)}.",
            "options": top_options
        }

    except Exception as e:
        return {"summary": f"API Error: {str(e)}", "options": []}

search_agent = Agent(
    role="Flight Search Expert",
    goal="Search for flights using the Duffel tool and return results.",
    backstory="You search for flights using API tools. You only report data from the tool, never invent flights.",
    tools=[search_duffel_flights],
    llm=fleeai_llm,
    verbose=True,
    cache=False
)

def create_search_task(query: FlightQuery) -> Task:
    """Creates a task for the agent to execute based on the user's FlightQuery."""
    origin_code = query.origin_iata or query.origin
    destination_code = query.destination_iata or query.destination

    return Task(
        description=(
            f"Search for flights using the 'Search and Filter Duffel Flights' tool.\n\n"
            f"Call the tool with:\n"
            f"- origin: {origin_code}\n"
            f"- destination: {destination_code}\n"
            f"- departure_date: {query.departure_date}\n"
            f"- preferences: {query.preferences}\n"
            f"- budget_inr: {query.budget_inr or 0}\n\n"
            f"Return the results exactly as the tool gives them. "
            f"For each flight, copy all fields (flight_id, airline, origin, destination, "
            f"departure_time, arrival_time, stops, duration_minutes, price_inr) from the tool output. "
            f"Add a short rank_reason for each flight."
        ),
        expected_output="A RankedFlights object with a summary and list of FlightOption objects.",
        agent=search_agent,
        output_pydantic=RankedFlights
    )


def run_flight_search(query: FlightQuery) -> RankedFlights:
    """
    Entry point used by the orchestrator (src/orchestrator.py::_run_search).

    This is the piece that was missing: the orchestrator does
    `from src.agents.search_agent import run_flight_search` and silently
    falls back to "Agent 2 not built yet" if this import fails -- which is
    exactly what was happening. Any genuine failure during the crew run
    (bad API key, network error, malformed LLM output, etc.) is allowed to
    propagate as a normal exception; the orchestrator's own try/except in
    _run_search_step() already turns that into a proper error message for
    the UI, so we don't want to swallow it here too.
    """
    task = create_search_task(query)
    crew = Crew(
        agents=[search_agent],
        tasks=[task],
        verbose=True,
        cache=False,
    )
    result = crew.kickoff()
    ranked: RankedFlights = result.pydantic
    # Fill in the query from Python — the LLM doesn't need to reproduce it
    ranked.query = query
    return ranked