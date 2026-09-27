"""
calendar-mcp: an MCP server exposing the `events` table in personal_assistant.db.

Same shape as tasks_mcp.py. Run it directly so a host (omp, Claude Desktop, the
MCP Inspector) can launch it over stdio:
    python calendar_mcp.py
"""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer

DB_PATH = Path(__file__).parent / "personal_assistant.db"

mcp = MCPServer("calendar")


class Event(TypedDict):
    id: int
    title: str
    start_time: str
    end_time: str | None
    location: str | None
    created_at: str


class FreeSlot(TypedDict):
    start: str
    end: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_event(row: sqlite3.Row) -> Event:
    return dict(row)  # type: ignore[return-value]


@mcp.tool()
def list_events(days_ahead: int = 7) -> list[Event]:
    """List upcoming events starting today, up to `days_ahead` days from now (default 7)."""
    conn = _connect()
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=days_ahead)).isoformat()
    rows = conn.execute(
        "SELECT * FROM events WHERE date(start_time) BETWEEN ? AND ? ORDER BY start_time",
        (today, until),
    ).fetchall()
    conn.close()
    return [_row_to_event(r) for r in rows]


@mcp.tool()
def add_event(
    title: str,
    start_time: str,
    end_time: str | None = None,
    location: str | None = None,
) -> Event:
    """Add a new calendar event.

    start_time and end_time should be ISO datetimes like '2026-09-25 14:00'.
    end_time may be omitted if unknown.
    """
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO events (title, start_time, end_time, location) VALUES (?, ?, ?, ?)",
        (title, start_time, end_time, location),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM events WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return _row_to_event(row)


@mcp.tool()
def find_free_slots(
    date_str: str,
    duration_minutes: int = 30,
    day_start: str = "09:00",
    day_end: str = "18:00",
) -> list[FreeSlot]:
    """Find open time slots on a given day.

    date_str is an ISO date like '2026-09-25'. Only considers the window between
    day_start and day_end (defaults 09:00-18:00), and only returns gaps at least
    duration_minutes long. An event with no end_time is treated as 30 minutes long.
    """
    conn = _connect()
    rows = conn.execute(
        "SELECT start_time, end_time FROM events WHERE date(start_time) = ? ORDER BY start_time",
        (date_str,),
    ).fetchall()
    conn.close()

    cursor = datetime.fromisoformat(f"{date_str} {day_start}")
    day_finish = datetime.fromisoformat(f"{date_str} {day_end}")

    busy: list[tuple[datetime, datetime]] = []
    for row in rows:
        start = datetime.fromisoformat(row["start_time"])
        end = (
            datetime.fromisoformat(row["end_time"])
            if row["end_time"]
            else start + timedelta(minutes=30)
        )
        busy.append((start, end))

    free: list[FreeSlot] = []
    for start, end in busy:
        gap = start - cursor
        if start > cursor and gap >= timedelta(minutes=duration_minutes):
            free.append({"start": cursor.strftime("%H:%M"), "end": start.strftime("%H:%M")})
        if end > cursor:
            cursor = end

    if day_finish > cursor and (day_finish - cursor) >= timedelta(minutes=duration_minutes):
        free.append({"start": cursor.strftime("%H:%M"), "end": day_finish.strftime("%H:%M")})

    return free


if __name__ == "__main__":
    mcp.run()
