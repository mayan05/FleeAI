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


# Define the CrewAI Agent
booking_agent = Agent(
    role="Booking & Confirmation Specialist",
    goal="Confirm the details of a selected flight and compile a booking order into a clear confirmation.",
    backstory=(
        "An meticulous airline booking desk agent AI. You NEVER invent a PNR, "
        "price, or status yourself -- you always call your tool to compile the "
        "order and then write a short, friendly itinerary summary from its output."
    ),
    tools=[simulate_booking_order],
    llm=fleeai_llm,
    verbose=True,
    cache=False,
)


def create_booking_task(selected_flight: FlightOption, passenger_count: int = 1) -> Task:
    """Creates a task for the agent to execute based on the user's selected FlightOption."""
    return Task(
        description=f"""
        Use the 'Simulate Flight Booking Order' tool to compile a booking order
        for this selected flight, then write a short, friendly itinerary summary.

        Input Data:
        - flight_id: {selected_flight.flight_id}
        - airline: {selected_flight.airline}
        - origin: {selected_flight.origin}
        - destination: {selected_flight.destination}
        - departure_time: {selected_flight.departure_time}
        - arrival_time: {selected_flight.arrival_time}
        - stops: {selected_flight.stops}
        - duration_minutes: {selected_flight.duration_minutes}
        - price_inr: {selected_flight.price_inr}
        - passenger_count: {passenger_count}

        Call the tool with flight_id, airline, origin, destination,
        departure_time, price_inr, and passenger_count. Then, using the
        tool's output plus the input data above, produce:
        - pnr, passenger_count, total_price_inr, status: copied EXACTLY
          from the tool's output. Do not alter or invent them.
        - itinerary_summary: a short (1-2 sentence) friendly confirmation
          mentioning airline, route, departure time, arrival time, stops,
          and total price.

        Do NOT attempt to output the full flight details as a structured
        object -- only the fields listed above.
        """,
        expected_output="pnr, passenger_count, total_price_inr, status (from the tool), and a short itinerary_summary.",
        agent=booking_agent,
        output_pydantic=BookingOrderOutput,
    )


def run_booking(selected_flight: FlightOption, passenger_count: int = 1) -> BookingConfirmation:
    """
    Entry point used by the orchestrator (src/orchestrator.py::_run_booking).

    Mirrors run_flight_search() in search_agent.py: any genuine failure
    during the crew run is allowed to propagate as a normal exception,
    since orchestrator._handle_flight_selection() already wraps this call
    in its own try/except and turns failures into a proper error message
    for the UI.

    The final BookingConfirmation.selected_flight is set directly from the
    `selected_flight` argument -- the same FlightOption instance the
    orchestrator already validated and passed in -- so all 10 of its
    fields are guaranteed present. Only pnr/passenger_count/
    total_price_inr/status/itinerary_summary come from the agent run.
    """
    task = create_booking_task(selected_flight, passenger_count)
    crew = Crew(
        agents=[booking_agent],
        tasks=[task],
        verbose=True,
        cache=False,
    )
    result = crew.kickoff()
    order: BookingOrderOutput = result.pydantic

    return BookingConfirmation(
        pnr=order.pnr,
        selected_flight=selected_flight,
        passenger_count=order.passenger_count,
        total_price_inr=order.total_price_inr,
        status=order.status,
        itinerary_summary=order.itinerary_summary,
    )