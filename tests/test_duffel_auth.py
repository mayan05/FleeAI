import os
import requests
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()
DUFFEL_TOKEN = os.getenv("DUFFEL_TOKEN")

def test_duffel_flight_search():
    print("Initiating Duffel sandbox flight search...")
    
    url = "https://api.duffel.com/air/offer_requests"
    
    headers = {
        "Authorization": f"Bearer {DUFFEL_TOKEN}",
        "Duffel-Version": "v2",
        "Content-Type": "application/json"
    }
    
    # Payload for searching a flight from Bengaluru (BLR) to Delhi (DEL)
    payload = {
        "data": {
            "slices": [
                {
                    "origin": "BLR",
                    "destination": "DEL",
                    "departure_date": "2026-07-20"
                }
            ],
            "passengers": [
                {"type": "adult"}
            ],
            "cabin_class": "economy"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract generated flight offers from sandbox airline
        offers = data.get("data", {}).get("offers", [])
        print(f"\nSuccess! Authenticated perfectly with Duffel Test Sandbox.")
        print(f"Found {len(offers)} simulated flight offers from Duffel Airways.")
        
        if offers:
            first_offer = offers[0]
            print("\nSnippet of Sample Offer:")
            print(f"  Total Amount: {first_offer.get('total_amount')} {first_offer.get('total_currency')}")
            print(f"  Allowed Passenger Types: {first_offer.get('passenger_identity_documents_required')}")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        if 'response' in locals() and response.text:
            print(f"API Error Response: {response.text}")

if __name__ == "__main__":
    if not DUFFEL_TOKEN:
        print("Error: DUFFEL_TOKEN missing from your .env file!")
    else:
        test_duffel_flight_search()