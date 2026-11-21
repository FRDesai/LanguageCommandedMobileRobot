"""Checks that run on the raw user text before the LLM sees it."""
import re

_STOP_WORDS = re.compile(r"\b(stop|halt|cancel)\b", re.IGNORECASE)

_OVERRIDE_PATTERNS = re.compile(
    r"\b(ignore|disregard|forget|override|bypass|disable)\b.{0,40}"
    r"\b(rules?|instructions?|safety|limits?|restrictions?|guardrails?|prompt)\b",
    re.IGNORECASE | re.DOTALL)


def is_stop_command(text: str) -> bool:
    """True if the message contains stop, halt or cancel as a whole word.

    Deliberately broad: a message that merely mentions stopping still stops the
    robot, because a missed stop is worse than an unneeded one.
    """
    return bool(_STOP_WORDS.search(text))


def looks_like_override(text: str) -> bool:
    """Heuristic flag for attempts to change the rules, used only for logging.

    Enforcement does not depend on it: the rules are code in tools.py.
    """
    return bool(_OVERRIDE_PATTERNS.search(text))
