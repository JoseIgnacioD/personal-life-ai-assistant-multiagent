"""
finance-mcp: an MCP server exposing the `transactions` table in personal_assistant.db.

Same shape as the other two servers. Run it directly so a host (omp, Claude
Desktop, the MCP Inspector) can launch it over stdio:
    python finance_mcp.py
"""
import sqlite3
from datetime import date
from pathlib import Path
from typing import TypedDict

from mcp.server import MCPServer

DB_PATH = Path(__file__).parent / "personal_assistant.db"

mcp = MCPServer("finance")


class Transaction(TypedDict):
    id: int
    amount: float
    category: str
    description: str | None
    date: str
    created_at: str


class CategoryTotal(TypedDict):
    category: str
    total: float


class MonthlySummary(TypedDict):
    month: str
    income: float
    expenses: float
    net: float
    by_category: list[CategoryTotal]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_transaction(row: sqlite3.Row) -> Transaction:
    return dict(row)  # type: ignore[return-value]


@mcp.tool()
def add_transaction(
    amount: float,
    category: str,
    description: str | None = None,
    date_str: str | None = None,
) -> Transaction:
    """Record a transaction.

    amount is positive for income, negative for an expense (e.g. -12.50 for a
    coffee, 1500 for a paycheck). date_str is an ISO date like '2026-09-25';
    if omitted, today is used.
    """
    conn = _connect()
    effective_date = date_str or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO transactions (amount, category, description, date) VALUES (?, ?, ?, ?)",
        (amount, category, description, effective_date),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return _row_to_transaction(row)


@mcp.tool()
def get_balance() -> float:
    """Return the current overall balance: the sum of every transaction ever recorded."""
    conn = _connect()
    total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions").fetchone()[0]
    conn.close()
    return total


@mcp.tool()
def monthly_summary(month: str) -> MonthlySummary:
    """Summarize income, expenses, and spending by category for one month.

    month is 'YYYY-MM', e.g. '2026-09'.
    """
    conn = _connect()
    pattern = f"{month}%"

    income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE date LIKE ? AND amount > 0",
        (pattern,),
    ).fetchone()[0]

    expenses = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE date LIKE ? AND amount < 0",
        (pattern,),
    ).fetchone()[0]

    by_category_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM transactions WHERE date LIKE ? "
        "GROUP BY category ORDER BY total",
        (pattern,),
    ).fetchall()
    conn.close()

    return {
        "month": month,
        "income": income,
        "expenses": expenses,
        "net": income + expenses,
        "by_category": [{"category": r["category"], "total": r["total"]} for r in by_category_rows],
    }


if __name__ == "__main__":
    mcp.run()
