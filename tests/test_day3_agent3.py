import sys
import os
from dotenv import load_dotenv
from src.schemas.models import FlightOption
from src.agents.booking_agent import run_booking

# NOTE: no litellm/Groq monkeypatch needed here -- the cache_breakpoint
# fix lives once, centrally, in src/llm_config.py and is picked up
# automatically via `from src.llm_config import fleeai_llm` inside
# booking_agent.py. See the comment block at the top of llm_config.py.
#
# NOTE (Day 4 fix): this test now calls run_booking() directly instead of
# building the Task/Crew itself and reading crew.kickoff().pydantic as a
# full BookingConfirmation. The crew's own output is now the narrower
# BookingOrderOutput (pnr/passenger_count/total_price_inr/status/
# itinerary_summary only) -- run_booking() is what assembles the real
# BookingConfirmation, using the original FlightOption object for
# selected_flight. Testing run_booking() end-to-end is what actually
# exercises the fix for the "4 validation errors for BookingConfirmation"
# bug.


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

    # 2. Run Agent 3 end-to-end
    confirmation = run_booking(test_flight, test_passenger_count)

    # 3. Print the final BookingConfirmation Pydantic output, and confirm
    #    selected_flight came through with every field intact.
    print("\n=== AGENT OUTPUT (BookingConfirmation) ===")
    print(confirmation.model_dump_json(indent=2))

    assert confirmation.selected_flight == test_flight, (
        "selected_flight was mutated/rebuilt instead of being passed through untouched"
    )
    print("\nselected_flight round-tripped with all fields intact.")


if __name__ == "__main__":
    run_standalone_test()