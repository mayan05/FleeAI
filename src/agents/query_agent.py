"""
Agent 1: Query Understanding Agent

Job: turn a messy natural-language flight request into a structured
FlightQuery object. If required info is missing, it does NOT guess —
it sets is_complete=False and produces a single clarification_question
for the orchestrator to relay back to the user.

Date handling: the LLM is NOT trusted to compute actual calendar dates
for relative phrases ("next Friday", "tomorrow") -- it only extracts the
phrase verbatim into raw_date_expression. The actual date math happens
afterward in resolve_relative_date(), which is deterministic Python and
therefore always correct.
"""

from datetime import date
from crewai import Agent, Task, Crew, Process
from src.llm_config import fleeai_llm
from src.schemas.models import FlightQuery
from src.utils.date_resolver import resolve_relative_date

query_understanding_agent = Agent(
    role="Flight Query Extractor",
    goal="Extract origin, destination, and departure date from a flight booking request.",
    backstory="You extract flight details from user messages into structured JSON.",
    llm=fleeai_llm,
    verbose=True,
    allow_delegation=False,
)


def build_extraction_task(user_request: str, conversation_context: str = "") -> Task:
    """
    Builds the extraction task for a given user message.

    conversation_context: pass in prior clarification Q&A here, so the agent
    has full context on multi-turn conversations (e.g. user answering a
    follow-up question).
    """
    context_block = (
        f"\n\nPrevious conversation:\n{conversation_context}\n"
        f"Use the answers above to fill in any missing fields."
        if conversation_context
        else ""
    )
    today_str = date.today().isoformat()

    return Task(
        description=(
            f"Today's date is {today_str}.\n\n"
            f"Extract flight details from this request:\n"
            f"\"{user_request}\"{context_block}\n\n"
            "Extract these fields:\n"
            "- origin: the departure city (e.g. \"Patna\", \"Delhi\")\n"
            "- destination: the arrival city\n"
            "- departure_date: date in YYYY-MM-DD format if given explicitly\n"
            "- raw_date_expression: if user said something like \"tomorrow\" or "
            "\"next Friday\", put the phrase here instead of departure_date\n"
            "- passengers: number of passengers (default 1)\n"
            "- budget_inr: budget in INR if mentioned, else null\n"
            "- cabin_class: economy/business/first (default economy)\n"
            "- preferences: list of preferences like [\"direct flights\"]\n"
            "- is_complete: true if origin AND destination AND (departure_date OR raw_date_expression) are all present\n"
            "- missing_fields: list of missing required fields\n"
            "- clarification_question: question to ask if is_complete is false\n\n"
            "Example — user says: \"fly from mumbai to delhi on 2026-08-01\"\n"
            "Output: origin=\"Mumbai\", destination=\"Delhi\", departure_date=\"2026-08-01\", "
            "is_complete=true, missing_fields=[]"
        ),
        expected_output="A FlightQuery JSON object.",
        agent=query_understanding_agent,
        output_pydantic=FlightQuery,
    )


def run_query_understanding(user_request: str, conversation_context: str = "") -> FlightQuery:
    """
    Runs Agent 1 and returns a validated, fully-resolved FlightQuery.

    After the LLM extracts the raw phrase, this function deterministically
    resolves raw_date_expression into a real departure_date. If resolution
    fails (unrecognized phrase), the query is forced back to incomplete
    with a clarification question, rather than silently leaving a bad date.
    """
    task = build_extraction_task(user_request, conversation_context)
    crew = Crew(
        agents=[query_understanding_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    query: FlightQuery = result.pydantic

    # Deterministic date resolution -- never trust the LLM's date math
    if query.departure_date is None and query.raw_date_expression:
        resolved = resolve_relative_date(query.raw_date_expression)
        if resolved:
            query.departure_date = resolved
        else:
            # Couldn't confidently resolve the phrase -- ask instead of guessing
            query.is_complete = False
            if "departure_date" not in query.missing_fields:
                query.missing_fields.append("departure_date")
            query.clarification_question = (
                f"I couldn't quite pin down '{query.raw_date_expression}' as a "
                f"date -- could you give me an exact date (e.g. 2026-07-17)?"
            )

    # Recompute completeness ourselves rather than trusting the LLM's flag --
    # it can be stale/wrong even when every required field is actually filled.
    query.missing_fields = [
        f for f in query.missing_fields
        if not (
            (f == "origin" and query.origin)
            or (f == "destination" and query.destination)
            or (f == "departure_date" and query.departure_date)
        )
    ]
    has_all_required = bool(query.origin and query.destination and query.departure_date)
    if has_all_required:
        query.is_complete = True
        query.missing_fields = []
        query.clarification_question = None
    else:
        query.is_complete = False
        if not query.origin and "origin" not in query.missing_fields:
            query.missing_fields.append("origin")
        if not query.destination and "destination" not in query.missing_fields:
            query.missing_fields.append("destination")
        if not query.departure_date and "departure_date" not in query.missing_fields:
            query.missing_fields.append("departure_date")
        if not query.clarification_question:
            query.clarification_question = (
                "Could you give me the missing details: "
                + ", ".join(query.missing_fields) + "?"
            )

    return query