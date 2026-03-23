# === Games Organ — games_server.py ===
# Handles conversational games inside Jarvis chat.
# Currently supports: Number Guessing Game
# Built: 03-21-26

import random
import logging

logger = logging.getLogger("games_server")

# ---------------------------------------------------------
# Game State — in-memory, single active game at a time
# ---------------------------------------------------------
_game_state = {
    "active":       False,
    "game_type":    None,
    "secret":       None,
    "attempts":     0,
    "max_attempts": 10,
}


def _reset_game():
    _game_state["active"]       = False
    _game_state["game_type"]    = None
    _game_state["secret"]       = None
    _game_state["attempts"]     = 0
    _game_state["max_attempts"] = 10


def is_game_active() -> bool:
    return _game_state["active"]


def start_number_game() -> str:
    _reset_game()
    _game_state["active"]    = True
    _game_state["game_type"] = "number_guess"
    _game_state["secret"]    = random.randint(1, 100)
    logger.info(f"[Games] Number game started. Secret={_game_state['secret']}")
    return (
        "Alright, I'm thinking of a number between 1 and 100. "
        "You have 10 attempts to guess it. Take your first guess!"
    )


def make_guess(user_input: str) -> str:
    if not _game_state["active"]:
        return "No game is active right now. Say 'start number game' to play."

    # Try to extract a number from the input
    words = user_input.replace(",", "").split()
    guess = None
    for word in words:
        try:
            guess = int(word)
            break
        except ValueError:
            continue

    if guess is None:
        return "I need a number to check your guess. What number are you thinking?"

    _game_state["attempts"] += 1
    attempts_used = _game_state["attempts"]
    attempts_left = _game_state["max_attempts"] - attempts_used
    secret = _game_state["secret"]

    # Correct guess
    if guess == secret:
        _reset_game()
        if attempts_used == 1:
            return f"Incredible! You got it in just 1 attempt! The number was {secret}. Well done!"
        return f"Correct! The number was {secret}. You got it in {attempts_used} attempts. Nice work!"

    # Out of attempts
    if attempts_left <= 0:
        _reset_game()
        if guess < secret:
            return f"Too low! Game over. The number was {secret}. Better luck next time! Say 'start number game' to play again."
        else:
            return f"Too high! Game over. The number was {secret}. Better luck next time! Say 'start number game' to play again."

    # Give hint
    direction = "Too low!" if guess < secret else "Too high!"
    if attempts_left == 1:
        return f"{direction} Last chance — {attempts_left} attempt left."
    return f"{direction} {attempts_left} attempts remaining."


def quit_game() -> str:
    if not _game_state["active"]:
        return "No game is currently running."
    secret = _game_state["secret"]
    _reset_game()
    return f"Game ended. The number was {secret}. Say 'start number game' whenever you want to play again."


# ---------------------------------------------------------
# Handle — MCP organ interface
# ---------------------------------------------------------
def handle(user_input: str) -> dict:
    text = user_input.lower().strip()

    # Quit game
    if any(k in text for k in ["quit game", "stop game", "end game", "exit game", "give up"]):
        return {"data": quit_game()}

    # Start number game
    if any(k in text for k in [
        "start number game", "number guessing game", "guessing game",
        "play a game", "lets play", "let's play", "start game",
        "number game"
    ]):
        return {"data": start_number_game()}

    # Active game — pass input as a guess
    if is_game_active():
        return {"data": make_guess(user_input)}

    return {"data": "I can play a number guessing game with you. Just say 'start number game' to begin!"}
