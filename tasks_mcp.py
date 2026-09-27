"""
tasks-mcp: an MCP server exposing the `tasks` table in personal_assistant.db.

Run it directly so a host (omp, Claude Desktop, the MCP Inspector) can launch
it over stdio:
    python tasks_mcp.py

Or open it in the Inspector while developing:
    uv run mcp dev tasks_mcp.py
"""
import sqlite3
from datetime import date
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer

DB_PATH = Path(__file__).parent / "personal_assistant.db"

mcp = MCPServer("tasks")


class Task(TypedDict):
    id: int
    title: str
    due_date: str | None
    priority: str
    done: int
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_task(row: sqlite3.Row) -> Task:
    return dict(row)  # type: ignore[return-value]


@mcp.tool()
def list_tasks(include_done: bool = False) -> list[Task]:
    """List tasks, soonest due date first. By default only shows tasks that aren't done yet."""
    conn = _connect()
    query = "SELECT * FROM tasks"
    if not include_done:
        query += " WHERE done = 0"
    query += " ORDER BY due_date IS NULL, due_date"
    rows = conn.execute(query).fetchall()
    conn.close()
    return [_row_to_task(r) for r in rows]


@mcp.tool()
def add_task(title: str, due_date: str | None = None, priority: str = "medium") -> Task:
    """Add a new task.

    due_date should be an ISO date like '2026-09-25', or omitted if there isn't one.
    priority must be 'low', 'medium', or 'high'.
    """
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO tasks (title, due_date, priority) VALUES (?, ?, ?)",
        (title, due_date, priority),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return _row_to_task(row)


@mcp.tool()
def complete_task(task_id: int) -> Task:
    """Mark a task as done, given its id."""
    conn = _connect()
    conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise ValueError(f"No task with id {task_id}")
    return _row_to_task(row)


@mcp.tool()
def list_overdue() -> list[Task]:
    """List tasks that are past their due date and not yet done."""
    conn = _connect()
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date < ? "
        "ORDER BY due_date",
        (today,),
    ).fetchall()
    conn.close()
    return [_row_to_task(r) for r in rows]


if __name__ == "__main__":
    mcp.run()
