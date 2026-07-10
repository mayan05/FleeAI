"""
Deterministic city name → IATA airport code mapping.

The LLM extracts city names like "Bangalore" or "Mumbai" from the user's
message, but the Duffel API needs 3-letter IATA codes (BLR, BOM).
Rather than asking the LLM to produce codes (it gets obscure ones wrong),
we resolve them here in plain Python -- same philosophy as date_resolver.py.

Coverage: major Indian cities + common aliases. Easy to extend.
"""

# Lowercase city name / alias → IATA code
_CITY_TO_IATA: dict[str, str] = {
    # Metro cities
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "bombay": "BOM",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "chennai": "MAA",
    "madras": "MAA",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "hyderabad": "HYD",
    # Tier-2 cities
    "pune": "PNQ",
    "ahmedabad": "AMD",
    "goa": "GOI",
    "panaji": "GOI",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "kochi": "COK",
    "cochin": "COK",
    "thiruvananthapuram": "TRV",
    "trivandrum": "TRV",
    "guwahati": "GAU",
    "chandigarh": "IXC",
    "patna": "PAT",
    "bhubaneswar": "BBI",
    "indore": "IDR",
    "coimbatore": "CJB",
    "nagpur": "NAG",
    "varanasi": "VNS",
    "srinagar": "SXR",
    "amritsar": "ATQ",
    "mangalore": "IXE",
    "mangaluru": "IXE",
    "visakhapatnam": "VTZ",
    "vizag": "VTZ",
    "ranchi": "IXR",
    "raipur": "RPR",
    "dehradun": "DED",
    "madurai": "IXM",
    "tiruchirappalli": "TRZ",
    "trichy": "TRZ",
    "udaipur": "UDR",
    "leh": "IXL",
    "bagdogra": "IXB",
    "siliguri": "IXB",
    "port blair": "IXZ",
    "imphal": "IMF",
    "agartala": "IXA",
    "dibrugarh": "DIB",
}

# Also accept raw IATA codes passed through (e.g. user says "BLR")
_KNOWN_IATA_CODES: set[str] = set(_CITY_TO_IATA.values())


def city_to_iata(city_name: str) -> str | None:
    """
    Resolve a city name or alias to its IATA airport code.

    Returns None if the city isn't in our mapping -- the orchestrator
    should then ask the user for clarification rather than guessing.
    """
    if not city_name:
        return None

    normalized = city_name.strip().lower()

    # If it's already an IATA code, pass it through
    if normalized.upper() in _KNOWN_IATA_CODES:
        return normalized.upper()

    return _CITY_TO_IATA.get(normalized)
