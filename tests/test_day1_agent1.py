"""
Day 1 test script — run this to confirm Agent 1 works end to end,
including the clarification loop for incomplete queries.

Usage:
    python test_day1_agent1.py
"""

from src.agents.query_agent import run_query_understanding

TEST_CASES = [
    # Complete query -> should NOT ask a clarification question
    "I wanna fly from Bangalore to Delhi next Friday, budget around 5000 rupees, just me",
    # Incomplete query -> should ask for the missing piece(s)
    "I need a flight to Mumbai sometime, nothing fancy",
]

def run_clarification_loop(user_request: str):
    print(f"\n{'='*70}\nUSER: {user_request}\n{'='*70}")

    query = run_query_understanding(user_request)
    context = ""

    # Keep looping until the query is complete or we hit a safety limit
    attempts = 0
    while not query.is_complete and attempts < 3:
        print(f"\n🤖 CLARIFICATION NEEDED: {query.clarification_question}")
        user_answer = input("Your answer (simulate the user here): ")
        context += f"\nQ: {query.clarification_question}\nA: {user_answer}"
        query = run_query_understanding(user_request, conversation_context=context)
        attempts += 1

    print("\n✅ FINAL STRUCTURED QUERY:")
    print(query.model_dump_json(indent=2))


if __name__ == "__main__":
    for case in TEST_CASES:
        run_clarification_loop(case)