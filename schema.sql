-- Tasks: things to do
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due_date TEXT,                              -- ISO date, e.g. '2026-09-25'
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    done INTEGER NOT NULL DEFAULT 0,             -- 0 = not done, 1 = done
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Events: calendar entries
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,                    -- ISO datetime, e.g. '2026-09-25 09:00'
    end_time TEXT,
    location TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Transactions: money in and out
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,                        -- positive = income, negative = expense
    category TEXT NOT NULL,                      -- e.g. 'food', 'transport', 'income'
    description TEXT,
    date TEXT NOT NULL,                          -- ISO date
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
