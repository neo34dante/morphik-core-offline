import re
from typing import Dict

# Predefined mapping of canonical location names to map URLs
LOCATION_URLS: Dict[str, str] = {
    "New Delhi": "http://localhost:5555/styles/basic-preview/#11/28.6139/77.2090",
    "Delhi": "http://localhost:5555/styles/basic-preview/#11/28.6139/77.2090",
    "Mumbai": "http://localhost:5555/styles/basic-preview/#11/19.0760/72.8777",
    "Kolkata": "http://localhost:5555/styles/basic-preview/#11/22.5726/88.3639",
    "Chennai": "http://localhost:5555/styles/basic-preview/#11/13.0827/80.2707",
    "Bengaluru": "http://localhost:5555/styles/basic-preview/#11/12.9716/77.5946",
    "Hanle": "http://localhost:5555/styles/basic-preview/#11/32.7900/79.0000",
    "Chumathang": "http://localhost:5555/styles/basic-preview/#11/33.3600/78.3400",
    "Karzok": "http://localhost:5555/styles/basic-preview/#11/32.9681/78.2640",
    "Nyoma": "http://localhost:5555/styles/basic-preview/#11/33.2059/78.6484",
    "Tso Moriri": "http://localhost:5555/styles/basic-preview/#10/32.9000/78.3000",
    "Chushul": "http://localhost:5555/styles/basic-preview/#11/33.6010/78.6480",
    "Pangong Tso": "http://localhost:5555/styles/basic-preview/#10/33.7179/78.8968",
}

# Detailed coordinates for supported Indian locations
INDIA_LOCATIONS = {
    "Delhi": {"lat": 28.6139, "lon": 77.2090, "zoom": 11},  # Delhi (city)
    "Mumbai": {"lat": 19.0760, "lon": 72.8777, "zoom": 11},  # Mumbai city
    "Kolkata": {"lat": 22.5726, "lon": 88.3639, "zoom": 11},  # Kolkata city
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "zoom": 11},  # Chennai city
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "zoom": 11},  # Bengaluru city
    "Leh": {"lat": 34.152588, "lon": 77.577049, "zoom": 11},
    "Ladakh": {"lat": 34.209515, "lon": 77.615112, "zoom": 6},
    "Hanle": {"lat": 32.790000, "lon": 79.000000, "zoom": 11},
    "Chumathang": {"lat": 33.360000, "lon": 78.340000, "zoom": 11},
    "Karzok": {"lat": 32.968125, "lon": 78.2639885, "zoom": 11},
    "Nyoma": {"lat": 33.2059163, "lon": 78.6483843, "zoom": 11},
    "Tso Moriri": {"lat": 32.900000, "lon": 78.300000, "zoom": 10},
    "Chushul": {"lat": 33.601000, "lon": 78.648000, "zoom": 11},
    "Pangong Tso": {"lat": 33.7179417, "lon": 78.8968000, "zoom": 10},
}


def _build_map_url(lat: float, lon: float, zoom: float) -> str:
    """Return a formatted map URL for the given coordinates."""
    return f"http://localhost:5555/styles/basic-preview/#{zoom:.2f}/{lat:.4f}/{lon:.4f}"


# Extend LOCATION_URLS with generated URLs for Indian locations
for _name, _info in INDIA_LOCATIONS.items():
    LOCATION_URLS[_name] = _build_map_url(_info["lat"], _info["lon"], _info["zoom"])

# Regular expression patterns that map various spellings to canonical names
LOCATION_PATTERNS: Dict[re.Pattern, str] = {
    re.compile(r"\bdelhi\b", re.IGNORECASE): "Delhi",
    re.compile(r"\bmumbai\b", re.IGNORECASE): "Mumbai",
    re.compile(r"\bkolkata\b", re.IGNORECASE): "Kolkata",
    re.compile(r"\bchennai\b", re.IGNORECASE): "Chennai",
    re.compile(r"\bbengaluru\b|\bbangalore\b", re.IGNORECASE): "Bengaluru",
    re.compile(r"\bleh\b", re.IGNORECASE): "Leh",
    re.compile(r"\bladakh\b", re.IGNORECASE): "Ladakh",
    re.compile(r"\bhanle\b", re.IGNORECASE): "Hanle",
    re.compile(r"\bchumathang\b", re.IGNORECASE): "Chumathang",
    re.compile(r"\bkarzok\b", re.IGNORECASE): "Karzok",
    re.compile(r"\bnyoma\b", re.IGNORECASE): "Nyoma",
    re.compile(r"\btso moriri\b", re.IGNORECASE): "Tso Moriri",
    re.compile(r"\bchushul\b", re.IGNORECASE): "Chushul",
    re.compile(r"\bpangong tso\b", re.IGNORECASE): "Pangong Tso",
}

def append_map_links(text: str) -> str:
    """Append map links for any detected locations in the text.

    If no locations are found, the original text is returned unchanged.
    """
    found_links = []
    for pattern, canonical in LOCATION_PATTERNS.items():
        if pattern.search(text):
            url = LOCATION_URLS.get(canonical)
            if url:
                found_links.append(f"{canonical}: {url}")

    if not found_links:
        return text

    links_text = "\n".join(found_links)
    if text and not text.endswith("\n"):
        text += "\n"
    return f"{text}\n{links_text}"