"""
Agent 3: Booking & Confirmation Agent

Job: take a FlightOption the user has already selected and produce a
BookingConfirmation. There's no real payment/order API here (Duffel's
live order endpoint needs a funded account + card), so "booking" is
simulated -- but the simulation itself (PNR generation, price totalling,
status) is deterministic Python, not something the LLM is trusted to
invent. The LLM's only job is to write a friendly itinerary_summary and
assemble the final object; every numeric/ID field comes straight from
the tool, same pattern as search_agent.py's Duffel tool.
"""

import random
import string

from crewai import Agent, Crew, Task
from crewai.tools import tool
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
        for this selected flight.
        Input Data:
        - flight_id: {selected_flight.flight_id}
        - airline: {selected_flight.airline}
        - origin: {selected_flight.origin}
        - destination: {selected_flight.destination}
        - departure_time: {selected_flight.departure_time}
        - price_inr: {selected_flight.price_inr}
        - passenger_count: {passenger_count}

        Review the tool's output. The fields pnr, passenger_count,
        total_price_inr, and status must come directly from the tool's
        output -- do not alter or invent them. Populate selected_flight
        with the original FlightOption exactly as given above. Only
        itinerary_summary should be written by you: a short (1-2 sentence)
        friendly confirmation summarizing airline, route, departure time,
        and total price.
        """,
        expected_output="A BookingConfirmation object with pnr, selected_flight, passenger_count, total_price_inr, status, and itinerary_summary.",
        agent=booking_agent,
        output_pydantic=BookingConfirmation,
    )


def run_booking(selected_flight: FlightOption, passenger_count: int = 1) -> BookingConfirmation:
    """
    Entry point used by the orchestrator (src/orchestrator.py::_run_booking).

    Mirrors run_flight_search() in search_agent.py: any genuine failure
    during the crew run is allowed to propagate as a normal exception,
    since orchestrator._handle_flight_selection() already wraps this call
    in its own try/except and turns failures into a proper error message
    for the UI.
    """
    task = create_booking_task(selected_flight, passenger_count)
    crew = Crew(
        agents=[booking_agent],
        tasks=[task],
        verbose=True,
        cache=False,
    )
    result = crew.kickoff()
    return result.pydantic