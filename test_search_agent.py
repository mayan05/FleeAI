import os
from dotenv import load_dotenv
from src.agents.search_agent import run_search_task

# Load your Duffel token
load_dotenv()

def test_standalone_search():
    print("Running standalone test for Flight Search & Ranking Agent...\n")
    
    # Hardcoded FlightQuery input as requested by Day 2 schedule
    hardcoded_query = {
        "origin": "BLR",
        "destination": "DEL",
        "date": "2026-07-20",
        "budget_inr": 15000,
        "preferences": "Prefer cheapest flights."
    }
    
    try:
        ranked_results = run_search_task(hardcoded_query)
        
        print("\n--- TEST SUCCESS ---")
        print(f"Summary: {ranked_results.summary}\n")
        
        if not ranked_results.options:
            print("No flights were found. (Empty results handled successfully).")
        else:
            for idx, flight in enumerate(ranked_results.options):
                print(f"Rank {idx + 1}: {flight.airline} | {flight.price} {flight.currency}")
                print(f"Reason: {flight.rank_reason}")
                print(f"Times: {flight.departure_time} to {flight.arrival_time}\n")
                
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    if not os.getenv("DUFFEL_TOKEN"):
        print("Error: DUFFEL_TOKEN missing!")
    else:
        test_standalone_search()