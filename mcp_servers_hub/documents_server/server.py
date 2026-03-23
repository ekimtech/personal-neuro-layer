# === Documents Organ — documents_server/server.py ===
# MCP handle() for router integration
# Triggers: generate invoice / estimate / letter

import logging

logger = logging.getLogger("documents_server")

_BASE_URL = "http://127.0.0.1:5000"

COMMANDS = {
    "invoice":  f"{_BASE_URL}/documents/invoice/create",
    "estimate": f"{_BASE_URL}/documents/estimate/create",
    "letter":   f"{_BASE_URL}/documents/letter/create",
    "list":     f"{_BASE_URL}/documents/",
}


def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # Invoice
    if any(k in text for k in ["invoice", "bill ", "billing"]):
        url = COMMANDS["invoice"]
        logger.info(f"[Docs] Invoice form → {url}")
        return {"data": f"Opening invoice form. Go here to fill it out: {url}"}

    # Estimate
    if any(k in text for k in ["estimate", "quote ", "quotation"]):
        url = COMMANDS["estimate"]
        logger.info(f"[Docs] Estimate form → {url}")
        return {"data": f"Opening estimate form. Go here to fill it out: {url}"}

    # Letter
    if any(k in text for k in ["letter", "correspondence"]):
        url = COMMANDS["letter"]
        logger.info(f"[Docs] Letter form → {url}")
        return {"data": f"Opening letter form. Go here to fill it out: {url}"}

    # List saved documents
    if any(k in text for k in ["list documents", "show documents", "my documents",
                                 "saved documents", "document list"]):
        url = COMMANDS["list"]
        return {"data": f"Here are your saved documents: {url}"}

    # Generic — offer all three
    return {"data": (
        f"Which document would you like to create?\n"
        f"- Invoice: {COMMANDS['invoice']}\n"
        f"- Estimate: {COMMANDS['estimate']}\n"
        f"- Letter: {COMMANDS['letter']}"
    )}
