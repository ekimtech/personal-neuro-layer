# internet_server/utils.py

import re

def extract_url(text: str) -> str | None:
    """
    Extract the first URL from a block of text.
    Used by the router to detect when a user message contains a URL.
    """
    if not text:
        return None

    url_pattern = r'(https?://[^\s]+)'
    match = re.search(url_pattern, text)
    return match.group(1) if match else None
