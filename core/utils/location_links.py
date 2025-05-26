import re
from typing import Dict

# Predefined mapping of canonical location names to map URLs
LOCATION_URLS: Dict[str, str] = {
    "New York City": "https://maps.google.com/?q=New+York+City",
    "Los Angeles": "https://maps.google.com/?q=Los+Angeles",
    "San Francisco": "https://maps.google.com/?q=San+Francisco",
}

# Regular expression patterns that map various spellings to canonical names
LOCATION_PATTERNS: Dict[re.Pattern, str] = {
    re.compile(r"\bnew york city\b|\bnyc\b", re.IGNORECASE): "New York City",
    re.compile(r"\blos angeles\b|\bla\b", re.IGNORECASE): "Los Angeles",
    re.compile(r"\bsan francisco\b|\bsf\b", re.IGNORECASE): "San Francisco",
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