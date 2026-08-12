import json
from pathlib import Path

_MENU_PATH = Path(__file__).resolve().parent.parent / "data" / "menu.json"


def load_menu() -> list[dict]:
    with open(_MENU_PATH) as f:
        return json.load(f)


def get_menu(category: str = "") -> str:
    """Look up menu items, optionally filtered by category.

    Args:
        category: Filter to this category (e.g. "appetizer", "main",
            "dessert"). Leave empty to return the full menu.
    """
    items = load_menu()
    if category:
        items = [item for item in items if item["category"] == category.lower()]
    if not items:
        return f"No menu items found for category '{category}'."
    return json.dumps(items, indent=2)
