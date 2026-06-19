import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'quantx.sqlite')


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _migrate_jobs_schema(conn: sqlite3.Connection) -> None:
    columns = {row['name'] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    if 'strategy_id' not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN strategy_id TEXT NOT NULL DEFAULT 'swing_ma_boll'")
    if 'strategy_params_json' not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN strategy_params_json TEXT NOT NULL DEFAULT '{}'")


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

        CREATE TABLE IF NOT EXISTS datahub_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_type TEXT NOT NULL,
            symbol TEXT,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            file_path TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            schema_version TEXT NOT NULL,
            source_name TEXT NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_datahub_cache_lookup
        ON datahub_cache(dataset_type, symbol, frequency, start_date, end_date);

        CREATE TABLE IF NOT EXISTS datahub_refreshes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_key TEXT NOT NULL,
            dataset_type TEXT NOT NULL,
            symbol TEXT,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            force_refresh INTEGER NOT NULL,
            status TEXT NOT NULL,
            cache_hit INTEGER NOT NULL DEFAULT 0,
            error_type TEXT,
            error_message TEXT,
            output_cache_path TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_datahub_refreshes_request_status
        ON datahub_refreshes(request_key, status);
        """
    )
    _migrate_jobs_schema(conn)
    conn.commit()
    return conn
