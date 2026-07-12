"""
FleeAI Orchestrator — the central pipeline coordinator.

Drives the multi-agent flow as a state machine:
    1. Query Understanding (Agent 1) — with clarification loop
    2. IATA resolution (deterministic Python)
    3. Flight Search & Ranking (Agent 2)
    4. Booking & Confirmation (Agent 3)

The UI (Streamlit or CLI) creates a FleeAISession and calls start() / respond()
to drive the conversation. The orchestrator returns OrchestratorResponse objects
that tell the UI exactly what to render next.
"""

from __future__ import annotations

import logging
from src.agents.query_agent import run_query_understanding
from src.schemas.models import (
    FlightQuery,
    FlightOption,
    RankedFlights,
    BookingConfirmation,
    OrchestratorResponse,
)
from src.utils.iata_lookup import city_to_iata

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ROUNDS = 5


def _resolve_iata_codes(query: FlightQuery) -> FlightQuery:
    """
    Fill in origin_iata / destination_iata from city names.
    If a city can't be mapped, mark the query incomplete so the UI
    can ask the user for clarification.
    """
    if query.origin:
        iata = city_to_iata(query.origin)
        if iata:
            query.origin_iata = iata
        else:
            query.is_complete = False
            query.clarification_question = (
                f"I don't recognise '{query.origin}' as a known airport city. "
                f"Could you give me the 3-letter airport code (e.g. BLR, DEL)?"
            )
            return query

    if query.destination:
        iata = city_to_iata(query.destination)
        if iata:
            query.destination_iata = iata
        else:
            query.is_complete = False
            query.clarification_question = (
                f"I don't recognise '{query.destination}' as a known airport city. "
                f"Could you give me the 3-letter airport code (e.g. BOM, CCU)?"
            )
            return query

    return query


def _run_search(query: FlightQuery) -> RankedFlights | None:
    """
    Try to use the real Agent 2 if available.
    Returns None if Agent 2 hasn't been built yet — the orchestrator
    will show the resolved FlightQuery and stop there.
    """
    try:
        from src.agents.search_agent import run_flight_search
        logger.info("Using real Agent 2 (search_agent) for flight search")
        return run_flight_search(query)
    except ImportError:
        logger.info("Agent 2 not available yet — stopping at query_complete")
        return None


def _run_booking(selected: FlightOption, passengers: int) -> BookingConfirmation | None:
    """
    Try to use the real Agent 3 if available.
    Returns None if booking_agent.py hasn't been built yet — the orchestrator
    will acknowledge the selection and show a clear placeholder.
    """
    try:
        from src.agents.booking_agent import run_booking
        logger.info("Using real Agent 3 (booking_agent) for booking")
        return run_booking(selected, passengers)
    except ImportError:
        logger.info("Agent 3 not available yet — showing booking placeholder")
        return None


class FleeAISession:
    """
    Stateful session for one user conversation.

    The UI creates one of these and calls start() with the initial message,
    then respond() with each follow-up answer. The returned OrchestratorResponse
    tells the UI what stage we're in and what to display.
    """

    def __init__(self):
        self.flight_query: FlightQuery | None = None
        self.ranked_flights: RankedFlights | None = None
        self.selected_flight: FlightOption | None = None
        self.conversation_context: str = ""
        self.original_request: str = ""
        self.clarification_count: int = 0
        self.stage: str = "idle"  # idle → understanding → results → select → booking → done

    def start(self, user_message: str) -> OrchestratorResponse:
        """Kick off a new flight search from a natural language request."""
        self.original_request = user_message
        self.conversation_context = ""
        self.clarification_count = 0
        self.stage = "understanding"
        return self._run_query_step(user_message)

    def respond(self, user_answer: str) -> OrchestratorResponse:
        """Handle a follow-up answer (clarification response or flight selection)."""
        if self.stage == "understanding":
            # User is answering a clarification question
            self.conversation_context += (
                f"\nQ: {self.flight_query.clarification_question if self.flight_query else '?'}"
                f"\nA: {user_answer}"
            )
            self.clarification_count += 1
            return self._run_query_step(self.original_request)

        if self.stage == "select":
            # User is picking a flight — Day 3 will handle booking
            return self._handle_flight_selection(user_answer)

        return OrchestratorResponse(
            stage="error",
            message="I wasn't expecting input at this point. Try starting a new search!",
        )

    def _run_query_step(self, user_message: str) -> OrchestratorResponse:
        """Run Agent 1 and handle the result."""
        if self.clarification_count >= MAX_CLARIFICATION_ROUNDS:
            return OrchestratorResponse(
                stage="error",
                message=(
                    "We've gone back and forth a few times and I still don't have "
                    "enough info. Could you try rephrasing your full request?"
                ),
            )

        try:
            self.flight_query = run_query_understanding(
                user_message, self.conversation_context
            )
        except Exception as e:
            logger.exception("Agent 1 failed")
            return OrchestratorResponse(
                stage="error",
                message=f"Something went wrong understanding your request: {e}",
            )

        if not self.flight_query.is_complete:
            self.stage = "understanding"
            return OrchestratorResponse(
                stage="clarification",
                message="I need a bit more info to search for flights.",
                clarification_question=self.flight_query.clarification_question,
                flight_query=self.flight_query,
            )

        # Query is complete — resolve IATA codes
        self.flight_query = _resolve_iata_codes(self.flight_query)
        if not self.flight_query.is_complete:
            # IATA resolution failed — ask for clarification
            self.stage = "understanding"
            return OrchestratorResponse(
                stage="clarification",
                message="I need to confirm an airport.",
                clarification_question=self.flight_query.clarification_question,
                flight_query=self.flight_query,
            )

        # All good — search for flights
        return self._run_search_step()

    def _run_search_step(self) -> OrchestratorResponse:
        """Run Agent 2 if available. If not, show the resolved query and stop."""
        self.stage = "searching"

        try:
            self.ranked_flights = _run_search(self.flight_query)
        except Exception as e:
            logger.exception("Agent 2 / flight search failed")
            return OrchestratorResponse(
                stage="error",
                message=f"Flight search failed: {e}",
            )

        # Agent 2 not available yet — show what Agent 1 produced
        if self.ranked_flights is None:
            self.stage = "done"
            return OrchestratorResponse(
                stage="query_complete",
                message=(
                    "✅ Query understood! Here's the structured output that "
                    "Agent 2 (Flight Search) will receive as input:"
                ),
                flight_query=self.flight_query,
            )

        if not self.ranked_flights.options:
            self.stage = "results"
            return OrchestratorResponse(
                stage="results",
                message=self.ranked_flights.summary,
                flight_query=self.flight_query,
                ranked_flights=self.ranked_flights,
            )

        self.stage = "select"
        return OrchestratorResponse(
            stage="results",
            message=self.ranked_flights.summary,
            flight_query=self.flight_query,
            ranked_flights=self.ranked_flights,
        )

    def _handle_flight_selection(self, user_input: str) -> OrchestratorResponse:
        """
        User picked a flight. Parse the selection, then call Agent 3 to book it.
        """
        if not self.ranked_flights or not self.ranked_flights.options:
            return OrchestratorResponse(
                stage="error",
                message="No flights available to select from.",
            )

        # Try to parse the selection as a number (1-indexed)
        try:
            idx = int(user_input.strip()) - 1
        except ValueError:
            return OrchestratorResponse(
                stage="select",
                message=f"Please enter a number between 1 and {len(self.ranked_flights.options)} to select a flight.",
                ranked_flights=self.ranked_flights,
            )

        if not (0 <= idx < len(self.ranked_flights.options)):
            return OrchestratorResponse(
                stage="select",
                message=f"Please enter a number between 1 and {len(self.ranked_flights.options)} to select a flight.",
                ranked_flights=self.ranked_flights,
            )

        self.selected_flight = self.ranked_flights.options[idx]
        passengers = self.flight_query.passengers if self.flight_query else 1

        # Run Agent 3
        self.stage = "booking"
        try:
            confirmation = _run_booking(self.selected_flight, passengers)
        except Exception as e:
            logger.exception("Agent 3 / booking failed")
            return OrchestratorResponse(
                stage="error",
                message=f"Booking failed: {e}",
            )

        # Agent 3 not available yet — acknowledge and show placeholder
        if confirmation is None:
            self.stage = "done"
            return OrchestratorResponse(
                stage="done",
                message=(
                    f"✅ You selected **{self.selected_flight.airline}** "
                    f"({self.selected_flight.origin} → {self.selected_flight.destination}) "
                    f"at ₹{self.selected_flight.price_inr:,}.\n\n"
                    f"🚧 Agent 3 (Booking) is being built by Shashank — "
                    f"confirmation will appear here once it lands!"
                ),
                flight_query=self.flight_query,
                ranked_flights=self.ranked_flights,
            )

        # Booking succeeded
        self.stage = "done"
        return OrchestratorResponse(
            stage="booking",
            message="Your flight has been booked! Here's your confirmation:",
            flight_query=self.flight_query,
            ranked_flights=self.ranked_flights,
            booking_confirmation=confirmation,
        )
