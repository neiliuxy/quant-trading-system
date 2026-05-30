import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'quantx.sqlite')


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL,
            status TEXT NOT NULL,
            symbol TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            cash REAL NOT NULL,
            use_market_filter INTEGER NOT NULL,
            risk_percent REAL NOT NULL,
            fast_ma INTEGER NOT NULL,
            slow_ma INTEGER NOT NULL,
            code_version TEXT NOT NULL,
            cache_hit INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_run_key_status ON jobs(run_key, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

        CREATE TABLE IF NOT EXISTS job_results (
            job_id INTEGER PRIMARY KEY,
            final_value REAL NOT NULL,
            total_return_pct REAL NOT NULL,
            max_drawdown_pct REAL NOT NULL,
            trade_count INTEGER NOT NULL,
            win_rate_pct REAL NOT NULL,
            artifact_path TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    return conn
