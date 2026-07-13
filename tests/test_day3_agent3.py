import sys
import os
from dotenv import load_dotenv
from crewai import Crew
from src.schemas.models import FlightOption
from src.agents.booking_agent import booking_agent, create_booking_task

# NOTE: no litellm/Groq monkeypatch needed here -- the cache_breakpoint
# fix lives once, centrally, in src/llm_config.py and is picked up
# automatically via `from src.llm_config import fleeai_llm` inside
# booking_agent.py. See the comment block at the top of llm_config.py.


def run_standalone_test():
    # 1. Hardcode a FlightOption for testing (as if Agent 2 had produced it
    #    and the user had just selected it in the UI).
    test_flight = FlightOption(
        flight_id="off_00009htYpSCXrwaB9DnUm2",
        airline="British Airways",
        origin="LHR",
        destination="JFK",
        departure_time="2026-08-15T10:30:00Z",
        arrival_time="2026-08-15T13:45:00Z",
        stops=0,
        duration_minutes=495,
        price_inr=142500,
        rank_reason="Cheapest direct option under budget.",
    )
    test_passenger_count = 2

    print(f"Testing Booking for: {test_flight.airline} ({test_flight.origin} -> {test_flight.destination})")

    # 2. Setup the Task and Crew
    task = create_booking_task(test_flight, test_passenger_count)
    crew = Crew(
        agents=[booking_agent],
        tasks=[task],
        verbose=True,
        cache=False,
    )

    # 3. Execute the Crew
    result = crew.kickoff()

    # 4. Print the final BookingConfirmation Pydantic output
    print("\n=== AGENT OUTPUT (BookingConfirmation) ===")
    print(result.pydantic.model_dump_json(indent=2))


if __name__ == "__main__":
    run_standalone_test()