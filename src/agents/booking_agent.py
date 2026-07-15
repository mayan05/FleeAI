"""
Agent 3: Booking & Confirmation Agent

Job: take a FlightOption the user has already selected and produce a
BookingConfirmation. There's no real payment/order API here (Duffel's
live order endpoint needs a funded account + card), so "booking" is
simulated -- but the simulation itself (PNR generation, price totalling,
status) is deterministic Python, not something the LLM is trusted to
invent. The LLM's only job is to write a friendly itinerary_summary;
every numeric/ID field comes straight from the tool, same pattern as
search_agent.py's Duffel tool.

--------------------------------------------------------------------
Day 4 bug fix:

The old version of this file asked the LLM to emit a *full*
BookingConfirmation via `output_pydantic=BookingConfirmation`, including
reconstructing the nested `selected_flight: FlightOption` object from
scratch. But the task prompt only ever told the LLM 6 of FlightOption's
10 fields (flight_id, airline, origin, destination, departure_time,
price_inr) -- arrival_time, stops, duration_minutes, and rank_reason
were never mentioned anywhere in the prompt. The LLM can't reproduce
data it was never given, so it emitted null for those 4 fields, and
Pydantic rejected them (they're required, non-Optional fields) --
exactly the 4-field validation error you were seeing.

The fix here isn't just "list all 10 fields in the prompt." Even with
every field listed, you'd still be trusting an LLM to retype a
structured object byte-for-byte (numbers, free-text rank_reason, etc.)
with no validation in between -- fragile by construction.

Instead: the LLM's output is now narrowed to just the 4 scalar fields
that legitimately come from *its* tool call (pnr, passenger_count,
total_price_inr, status) plus the one field it's actually meant to
author (itinerary_summary). `run_booking()` then builds the final
BookingConfirmation in plain Python, using the *original* FlightOption
object it already holds in memory for `selected_flight`. That object
never goes through the LLM, so none of its fields can be dropped.
--------------------------------------------------------------------
"""

import random
import string

from crewai import Agent, Crew, Task
from crewai.tools import tool
from pydantic import BaseModel, Field

from src.llm_config import fleeai_llm
from src.schemas.models import FlightOption, BookingConfirmation


def _generate_pnr() -> str:
    """6-character alphanumeric PNR, uppercase letters + digits (airline-style)."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


@tool("Simulate Flight Booking Order")
def simulate_booking_order(
    flight_id: str,
    airline: str,
    origin: str,
    destination: str,
    departure_time: str,
    price_inr: str,
    passenger_count: str = "1",
) -> dict:
    """Simulates compiling a booking order for a selected flight.
    Pass price_inr and passenger_count as numeric strings. Generates a
    PNR and computes the total price deterministically -- this is a
    simulation (no real Duffel order/payment call), so pricing and PNR
    logic must not be left to the LLM.
    """
    try:
        price = float(price_inr)
    except ValueError:
        price = 0.0

    try:
        passengers = max(1, int(passenger_count))
    except ValueError:
        passengers = 1

    return {
        "pnr": _generate_pnr(),
        "flight_id": flight_id,
        "airline": airline,
        "origin": origin,
        "destination": destination,
        "departure_time": departure_time,
        "passenger_count": passengers,
        "total_price_inr": round(price * passengers),
        "status": "CONFIRMED",
    }


class BookingOrderOutput(BaseModel):
    """
    What the agent is actually responsible for producing.

    Deliberately does NOT include `selected_flight` (a FlightOption).
    That field is filled in deterministically by run_booking() from the
    FlightOption object already sitting in Python memory -- never by
    asking the LLM to retype it. This is what fixes the Day 4 bug: there
    is no longer any path where arrival_time/stops/duration_minutes/
    rank_reason have to survive an LLM round-trip.
    """

    pnr: str = Field(description="Exactly the pnr returned by the tool -- do not alter or invent")
    passenger_count: int = Field(description="Exactly the passenger_count returned by the tool")
    total_price_inr: int = Field(description="Exactly the total_price_inr returned by the tool")
    status: str = Field(description="Exactly the status returned by the tool")
    itinerary_summary: str = Field(
        description="Short (1-2 sentence) friendly confirmation you write yourself, "
        "summarizing airline, route, departure/arrival time, stops, and total price."
    )


booking_agent = Agent(
    role="Booking Specialist",
    goal="Book a flight by calling the booking tool and returning the confirmation.",
    backstory="You book flights by calling your tool. Never invent a PNR or price — always use the tool.",
    tools=[simulate_booking_order],
    llm=fleeai_llm,
    verbose=True,
    cache=False,
)


def create_booking_task(selected_flight: FlightOption, passenger_count: int = 1) -> Task:
    """Creates a task for the agent to execute based on the user's selected FlightOption."""
    return Task(
        description=(
            f"Book this flight using the 'Simulate Flight Booking Order' tool.\n\n"
            f"Call the tool with:\n"
            f"- flight_id: {selected_flight.flight_id}\n"
            f"- airline: {selected_flight.airline}\n"
            f"- origin: {selected_flight.origin}\n"
            f"- destination: {selected_flight.destination}\n"
            f"- departure_time: {selected_flight.departure_time}\n"
            f"- price_inr: {selected_flight.price_inr}\n"
            f"- passenger_count: {passenger_count}\n\n"
            f"From the tool's output, return:\n"
            f"- pnr: exactly as returned by the tool\n"
            f"- passenger_count: exactly as returned\n"
            f"- total_price_inr: exactly as returned\n"
            f"- status: exactly as returned\n"
            f"- itinerary_summary: write a short 1-2 sentence confirmation mentioning "
            f"the airline, route, and price"
        ),
        expected_output="pnr, passenger_count, total_price_inr, status, and itinerary_summary.",
        agent=booking_agent,
        output_pydantic=BookingOrderOutput,
    )


def run_booking(selected_flight: FlightOption, passenger_count: int = 1) -> BookingConfirmation:
    """
    Entry point used by the orchestrator (src/orchestrator.py::_run_booking).

    Calls the booking tool directly from Python — no LLM needed.
    The tool is pure deterministic logic (PNR generation, price math),
    so routing it through a slow local model just adds latency and
    unreliability (the 3B model was failing to extract the PNR).
    """
    # Call the tool function directly — same function the agent would call
    tool_result = simulate_booking_order.func(
        flight_id=selected_flight.flight_id,
        airline=selected_flight.airline,
        origin=selected_flight.origin,
        destination=selected_flight.destination,
        departure_time=selected_flight.departure_time,
        price_inr=str(selected_flight.price_inr),
        passenger_count=str(passenger_count),
    )

    # Build the itinerary summary in plain Python
    stops_text = "Direct" if selected_flight.stops == 0 else f"{selected_flight.stops} stop(s)"
    itinerary = (
        f"Your {tool_result['airline']} flight from {tool_result['origin']} to "
        f"{tool_result['destination']} departs at {selected_flight.departure_time}. "
        f"{stops_text}, {tool_result['passenger_count']} passenger(s), "
        f"total ₹{tool_result['total_price_inr']:,}."
    )

    return BookingConfirmation(
        pnr=tool_result["pnr"],
        selected_flight=selected_flight,
        passenger_count=tool_result["passenger_count"],
        total_price_inr=tool_result["total_price_inr"],
        status=tool_result["status"],
        itinerary_summary=itinerary,
    )