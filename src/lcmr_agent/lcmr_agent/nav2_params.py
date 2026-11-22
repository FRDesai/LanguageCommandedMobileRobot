"""Applies this project's changes on top of TurtleBot3's stock Nav2 parameters."""


def merge(stock: dict, changes: dict) -> dict:
    """Return the stock parameters with the changes applied.

    Nested sections are merged key by key; any other value (numbers, strings,
    lists) replaces the stock one whole.
    """
    merged = dict(stock)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged
