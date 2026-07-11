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
def search_duffel_flights(origin: str, destination: str, departure_date: str, preferences: str, budget_inr: float | None = None) -> dict:
    """Searches Duffel API for flights and filters them by budget and preferences."""
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

        # Deterministic Python logic: Filter by budget using dictionary access
        # Deterministic Python logic: Filter by budget using dictionary access.
        # No budget given by the user -> treat as "no cap" instead of failing.
        effective_budget = budget_inr if budget_inr is not None else float("inf")

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
            return {"summary": f"Flights found, but none under the budget of {budget_inr} INR.", "options": []}

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

# Define the CrewAI Agent
search_agent = Agent(
    role="Flight Search & Ranking Expert",
    goal="Search for flights using Duffel and rank them based on user preferences.",
    backstory="An expert travel agent AI that uses API tools to find the best flights. You NEVER invent flight data. You only use the data provided by your tools.",
    tools=[search_duffel_flights],
    llm=fleeai_llm,
    verbose=True,
    cache=False
)

def create_search_task(query: FlightQuery) -> Task:
    """Creates a task for the agent to execute based on the user's FlightQuery."""
    # Duffel's API requires 3-letter IATA codes, not city names. The
    # orchestrator resolves origin_iata/destination_iata deterministically
    # in Python (src/utils/iata_lookup.py) before Agent 2 ever runs -- use
    # those. Falling back to query.origin/destination keeps this working
    # for standalone tests that hardcode an IATA code directly into origin
    # (e.g. tests/test_day2_agent2.py uses origin="LHR") without going
    # through the orchestrator's resolution step at all.
    origin_code = query.origin_iata or query.origin
    destination_code = query.destination_iata or query.destination

    return Task(
        description=f"""
        Use the 'Search and Filter Duffel Flights' tool to find flights.
        Input Data:
        - Origin: {origin_code}
        - Destination: {destination_code}
        - Date: {query.departure_date}
        - Budget: {query.budget_inr}
        - Preferences: {query.preferences}

        Review the tool's output. Every field in each FlightOption -- including
        origin, destination, stops, duration_minutes, and price_inr -- must come
        directly from the tool's output. Only 'rank_reason' should be written by
        you, explaining why that option fits the user's preferences.
        If no flights are found, output the empty summary provided by the tool.
        """,
        expected_output="A RankedFlights object containing a summary and a list of FlightOption objects.",
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
    return result.pydantic