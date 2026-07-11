import sys
import os
from dotenv import load_dotenv
from crewai import Crew
from src.schemas.models import FlightQuery
from src.agents.search_agent import search_agent, create_search_task

# NOTE: no litellm monkeypatch needed here anymore. The Groq /
# cache_breakpoint fix now lives once, centrally, in src/llm_config.py
# (it patches crewai.llms.cache.mark_cache_breakpoint at import time,
# before any agent is constructed), and every agent module -- including
# search_agent.py -- picks it up automatically via `from src.llm_config
# import fleeai_llm`. See the comment block at the top of llm_config.py
# for the full explanation.


def run_standalone_test():
    # 1. Hardcode a FlightQuery for testing
    test_query = FlightQuery(
        origin="LHR",
        destination="JFK",
        departure_date="2026-08-15",
        budget_inr=150000.0,
        preferences=["cheapest"],
        is_complete=True
    )

    print(f"Testing Flight Search for: {test_query.origin} to {test_query.destination}")

    # 2. Setup the Task and Crew
    task = create_search_task(test_query)
    crew = Crew(
        agents=[search_agent],
        tasks=[task],
        verbose=True,
        cache=False
    )

    # 3. Execute the Crew
    result = crew.kickoff()

    # 4. Print the final RankedFlights Pydantic output
    print("\n=== AGENT OUTPUT (RankedFlights) ===")
    print(result.pydantic.model_dump_json(indent=2))


if __name__ == "__main__":
    run_standalone_test()
