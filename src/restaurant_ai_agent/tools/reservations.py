import itertools

_next_id = itertools.count(1)
_reservations: dict[int, dict] = {}


def book_reservation(name: str, party_size: int, time: str) -> str:
    """Book a table reservation.

    Args:
        name: Name the reservation is under.
        party_size: Number of guests.
        time: Requested date and time, in any human-readable format
            (e.g. "2026-08-14 19:30" or "Friday at 7:30pm").
    """
    reservation_id = next(_next_id)
    _reservations[reservation_id] = {
        "id": reservation_id,
        "name": name,
        "party_size": party_size,
        "time": time,
    }
    return f"Reservation #{reservation_id} confirmed for {name}, party of {party_size}, at {time}."


def list_reservations() -> str:
    """List all current reservations."""
    if not _reservations:
        return "No reservations on file."
    lines = [
        f"#{r['id']}: {r['name']}, party of {r['party_size']}, at {r['time']}"
        for r in _reservations.values()
    ]
    return "\n".join(lines)


def cancel_reservation(reservation_id: int) -> str:
    """Cancel an existing reservation by ID.

    Args:
        reservation_id: The reservation number to cancel.
    """
    if reservation_id not in _reservations:
        return f"No reservation found with ID {reservation_id}."
    del _reservations[reservation_id]
    return f"Reservation #{reservation_id} has been cancelled."
