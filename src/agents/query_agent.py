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
    role="Flight Query Analyst",
    goal=(
        "Extract precise, structured flight search parameters from a user's "
        "natural language request. Never invent information the user did not "
        "provide -- if origin, destination, or departure date is missing or "
        "ambiguous, flag it clearly instead of guessing."
    ),
    backstory=(
        "You are a meticulous travel-desk analyst. You've seen every way people "
        "describe travel plans -- vague dates, city nicknames, budget ranges -- "
        "and you're excellent at pulling out exactly what's needed for a flight "
        "search while knowing when to ask instead of assume. You know you are "
        "bad at mental weekday arithmetic, so you never try to calculate an "
        "actual date from a phrase like 'next Friday' -- you just capture the "
        "phrase exactly as the user said it and let a separate system resolve "
        "it precisely."
    ),
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
        f"\n\nIMPORTANT: The user has already answered a clarification "
        f"question. You MUST extract origin, destination, and date info from "
        f"this answer and merge it with the original request below -- do not "
        f"ask the same question again if the answer already covers it.\n"
        f"{conversation_context}"
        if conversation_context
        else ""
    )
    today_str = date.today().isoformat()

    return Task(
        description=(
            f"Today's date is {today_str}. Do NOT use this to calculate a "
            f"final date yourself -- see date rules below.\n\n"
            f"Analyze this flight booking request and extract structured search "
            f"parameters.\n\nUser request: \"{user_request}\"{context_block}\n\n"
            "Rules:\n"
            "- origin, destination, and a date (either departure_date OR "
            "raw_date_expression) are REQUIRED to consider the query complete.\n"
            "- DATE HANDLING: if the user gave an explicit calendar date "
            "('July 20', '20th', '2026-07-20'), put the resolved YYYY-MM-DD in "
            "departure_date. If the user gave a RELATIVE phrase ('next "
            "Friday', 'tomorrow', 'in 2 weeks'), do NOT calculate a date "
            "yourself -- copy the phrase verbatim into raw_date_expression and "
            "leave departure_date null. You are unreliable at weekday math, so "
            "never attempt it.\n"
            "- CRITICAL: If the user's message does not explicitly state an "
            "origin city, destination city, or any date/date-phrase, you MUST "
            "leave that field as null and add it to missing_fields. Never "
            "infer, assume, or invent an origin, destination, or date the "
            "user did not explicitly say -- even if one seems 'likely'.\n\n"
            "EXAMPLE OF WHAT NOT TO DO:\n"
            "User request: \"I need a flight to Mumbai sometime, nothing fancy\"\n"
            "WRONG output: origin=\"Bangalore\", departure_date=\"2026-07-14\", "
            "is_complete=true  <-- WRONG, user never said an origin, and "
            "'sometime' is not a real date.\n"
            "CORRECT output: origin=null, destination=\"Mumbai\", "
            "departure_date=null, raw_date_expression=null, is_complete=false, "
            "missing_fields=[\"origin\", \"departure_date\"], "
            "clarification_question=\"Which city will you be flying from, and "
            "do you have a date in mind?\"\n\n"
            "- Do not fabricate a budget, passenger count, or preference the "
            "user never mentioned -- passengers defaults to 1, cabin_class "
            "defaults to 'economy' only if not specified.\n"
            "- If anything required is missing, set is_complete to false, list "
            "the missing fields, and write exactly ONE clear, friendly "
            "clarification question covering all missing pieces at once."
        ),
        expected_output="A FlightQuery JSON object matching the schema exactly.",
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