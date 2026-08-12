import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from restaurant_ai_agent.tools.menu import get_menu
from restaurant_ai_agent.tools.reservations import (
    book_reservation,
    cancel_reservation,
    list_reservations,
)


def test_get_menu_returns_all_items_by_default():
    items = json.loads(get_menu())
    assert len(items) > 0


def test_get_menu_filters_by_category():
    items = json.loads(get_menu("dessert"))
    assert all(item["category"] == "dessert" for item in items)


def test_get_menu_unknown_category():
    result = get_menu("not-a-category")
    assert "No menu items found" in result


def test_book_and_cancel_reservation():
    confirmation = book_reservation("Alex", 4, "2026-08-14 19:30")
    assert "confirmed" in confirmation

    listing = list_reservations()
    assert "Alex" in listing

    reservation_id = int(confirmation.split("#")[1].split()[0])
    cancellation = cancel_reservation(reservation_id)
    assert "cancelled" in cancellation
