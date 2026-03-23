# internet_server/intents.py

# INTENTS for internet_server
# The router will load these and inject "server": "internet_server"

INTENTS = [
    {
        "name": "weather",
        "patterns": [
            r"\bweather\b",
            r"\bforecast\b",
            r"\btemperature\b",
            r"\brain\b",
            r"\bsunny\b",
            r"\bcloudy\b",
            r"weather in (.*)",
            r"what(?:'s| is) the weather(?: in)? (.*)",
        ],
        "action": "get_weather",
        "fields": ["location"],
    },
    {
        "name": "web_search",
        "patterns": [
            r"\bsearch for (.+)",
            r"\blook up (.+)",
            r"\bfind (.+)",
            r"\bgoogle (.+)",
            r"\bweb search\b",
        ],
        "action": "web_search",
        "fields": ["query"],
    },
    {
        "name": "fetch_page",
        "patterns": [
            r"\bread\b .*https?://\S+",
            r"\bopen\b .*https?://\S+",
            r"\bfetch\b .*https?://\S+",
            r"https?://\S+",
        ],
        "action": "fetch_page",
        "fields": ["url"],
    },
    {
        "name": "news",
        "patterns": [
            r"\bnews\b",
            r"\bheadlines\b",
            r"what(?:'s| is) happening\b",
            r"latest news",
        ],
        "action": "get_news",
        "fields": ["query"],
    },
]
