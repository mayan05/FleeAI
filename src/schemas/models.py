"""
Shared data contracts between FleeAI's 3 agents.

Agent 1 (Query Understanding) produces -> FlightQuery
Agent 2 (Search & Ranking) consumes FlightQuery, produces -> RankedFlights
Agent 3 (Booking) consumes a chosen FlightOption, produces -> BookingConfirmation

Keeping these in one file means both Mayan and Shashank are coding against
the exact same structure, so their agents plug together without surprises.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class FlightQuery(BaseModel):
    """Structured output of the Query Understanding Agent (Agent 1)."""

    origin: Optional[str] = Field(
        default=None, description="Departure city or IATA airport code, e.g. 'Bangalore' or 'BLR'"
    )
    destination: Optional[str] = Field(
        default=None, description="Arrival city or IATA airport code, e.g. 'Delhi' or 'DEL'"
    )
    departure_date: Optional[str] = Field(
        default=None,
        description="Departure date in YYYY-MM-DD format, ONLY if the user gave "
        "an explicit calendar date (e.g. 'July 20', '2026-07-20'). Leave null "
        "if the user used a relative phrase like 'next Friday' -- put that "
        "phrase in raw_date_expression instead.",
    )
    raw_date_expression: Optional[str] = Field(
        default=None,
        description="The user's exact relative date phrase verbatim, e.g. "
        "'next Friday', 'tomorrow', 'in 2 weeks'. Only set this if "
        "departure_date could not be filled with an explicit date. Do NOT "
        "attempt to calculate an actual date yourself for relative phrases.",
    )
    return_date: Optional[str] = Field(
        default=None, description="Return date in YYYY-MM-DD format, if round trip"
    )
    origin_iata: Optional[str] = Field(
        default=None,
        description="3-letter IATA code for origin airport, resolved deterministically from origin city name",
    )
    destination_iata: Optional[str] = Field(
        default=None,
        description="3-letter IATA code for destination airport, resolved deterministically from destination city name",
    )
    passengers: int = Field(default=1, description="Number of passengers")
    budget_inr: Optional[int] = Field(
        default=None, description="Max budget in INR, if the user mentioned one"
    )
    cabin_class: Optional[str] = Field(
        default="economy", description="economy / premium_economy / business / first"
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="Free-form preferences, e.g. ['direct flights only', 'morning departure']",
    )
    is_complete: bool = Field(
        description="True only if origin, destination, and departure_date are all present"
    )
    missing_fields: List[str] = Field(
        default_factory=list, description="List of required fields still missing"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="A single natural-language question to ask the user if is_complete is False",
    )


class FlightOption(BaseModel):
    """A single flight result, as produced by Agent 2."""

    flight_id: str
    airline: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    stops: int
    duration_minutes: int
    price_inr: int
    rank_reason: str = Field(
        description="Short natural-language explanation of why this option was ranked here"
    )


class RankedFlights(BaseModel):
    """Structured output of the Flight Search & Ranking Agent (Agent 2)."""

    query: Optional[FlightQuery] = Field(default=None, description="The original query — filled in by Python, not the LLM")
    options: List[FlightOption]
    summary: str = Field(description="1-2 sentence natural-language summary of the results")


class BookingConfirmation(BaseModel):
    """Structured output of the Booking & Confirmation Agent (Agent 3)."""

    pnr: str
    selected_flight: FlightOption
    passenger_count: int
    total_price_inr: int
    status: str = Field(description="CONFIRMED / PENDING / CANCELLED")
    itinerary_summary: str


class OrchestratorResponse(BaseModel):
    """What the orchestrator returns to the UI after each interaction."""

    stage: Literal["clarification", "searching", "query_complete", "results", "select", "booking", "done", "error", "reset"] = Field(
        description="Current stage of the pipeline, tells the UI what to render"
    )
    message: str = Field(
        description="Human-readable message to display to the user"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Follow-up question for the user, set when stage='clarification'",
    )
    flight_query: Optional[FlightQuery] = Field(
        default=None, description="The resolved flight query, available once complete"
    )
    ranked_flights: Optional[RankedFlights] = Field(
        default=None, description="Search results, available when stage='results' or 'select'"
    )
    booking_confirmation: Optional[BookingConfirmation] = Field(
        default=None, description="Booking result from Agent 3, available when stage='booking' or 'done'"
    )