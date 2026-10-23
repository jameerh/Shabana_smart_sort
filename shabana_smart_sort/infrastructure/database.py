"""SQLite database manager and migration runner."""
import sqlite3
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("ShabanaSmartSort.Database")


class DatabaseManager:
    """Thread-safe SQLite database manager with WAL mode and auto-migrations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local SQLite connection with row factory enabled."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable Foreign Keys & Write-Ahead-Logging for responsiveness
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        """Closes the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def init_database(self) -> None:
        """Initializes database schema and runs initial migrations."""
        with self._lock:
            conn = self.get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
                """)
            self._apply_migrations(conn)

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """Applies versioned schema migrations."""
        cur = conn.cursor()
        cur.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
        applied = {row[0] for row in cur.fetchall()}

        # Migration 1: Initial core schema
        if 1 not in applied:
            logger.info("Applying migration 1: Core tables creation")
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS app_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        priority INTEGER NOT NULL DEFAULT 100,
                        is_enabled INTEGER NOT NULL DEFAULT 1,
                        logical_op TEXT NOT NULL DEFAULT 'all',
                        action_json TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rule_conditions (
                        id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        target TEXT NOT NULL,
                        operator TEXT NOT NULL,
                        value TEXT NOT NULL,
                        case_sensitive INTEGER NOT NULL DEFAULT 0,
                        description TEXT,
                        FOREIGN KEY(rule_id) REFERENCES rules(id) ON DELETE CASCADE
                    );
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rule_conditions_rule_id
                    ON rule_conditions(rule_id);
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scan_jobs (
                        id TEXT PRIMARY KEY,
                        root_path TEXT NOT NULL,
                        is_recursive INTEGER NOT NULL DEFAULT 0,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        total_files INTEGER NOT NULL DEFAULT 0,
                        total_size_bytes INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        error_message TEXT
                    );
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sort_jobs (
                        id TEXT PRIMARY KEY,
                        scan_job_id TEXT,
                        source_folder TEXT NOT NULL,
                        target_folder TEXT NOT NULL,
                        is_dry_run INTEGER NOT NULL DEFAULT 1,
                        total_operations INTEGER NOT NULL DEFAULT 0,
                        succeeded_operations INTEGER NOT NULL DEFAULT 0,
                        failed_operations INTEGER NOT NULL DEFAULT 0,
                        skipped_operations INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        journal_notes TEXT
                    );
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS planned_operations (
                        id TEXT PRIMARY KEY,
                        sort_job_id TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        destination_path TEXT NOT NULL,
                        original_destination_path TEXT NOT NULL,
                        action TEXT NOT NULL DEFAULT 'move',
                        matched_rule_id TEXT,
                        matched_rule_name TEXT,
                        match_reason TEXT,
                        is_valid INTEGER NOT NULL DEFAULT 1,
                        validation_error TEXT,
                        collision_detected INTEGER NOT NULL DEFAULT 0,
                        collision_policy_applied TEXT NOT NULL,
                        selected_for_execution INTEGER NOT NULL DEFAULT 1,
                        file_size INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL,
                        executed_at TEXT,
                        error_message TEXT,
                        is_cross_volume INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(sort_job_id) REFERENCES sort_jobs(id) ON DELETE CASCADE
                    );
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_planned_ops_job_id
                    ON planned_operations(sort_job_id);
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operation_journal (
                        id TEXT PRIMARY KEY,
                        operation_id TEXT NOT NULL,
                        sort_job_id TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        destination_path TEXT NOT NULL,
                        action TEXT NOT NULL DEFAULT 'move',
                        status TEXT NOT NULL,
                        file_size INTEGER NOT NULL DEFAULT 0,
                        is_cross_volume INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        executed_at TEXT,
                        reverted_at TEXT,
                        sha256_before TEXT,
                        sha256_after TEXT,
                        temp_path TEXT,
                        error_message TEXT,
                        can_undo INTEGER NOT NULL DEFAULT 1,
                        undo_status TEXT,
                        FOREIGN KEY(sort_job_id) REFERENCES sort_jobs(id) ON DELETE CASCADE
                    );
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_op_journal_job_id
                    ON operation_journal(sort_job_id);
                """)

                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (1, datetime('now'));"
                )

        # Migration 2: Rule condition groups and content index cache
        if 2 not in applied:
            logger.info("Applying migration 2: Rule condition groups and content cache")
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS rule_groups (
                        id TEXT PRIMARY KEY,
                        rule_id TEXT NOT NULL,
                        logical_op TEXT NOT NULL DEFAULT 'all',
                        group_order INTEGER NOT NULL DEFAULT 0,
                        description TEXT,
                        FOREIGN KEY(rule_id) REFERENCES rules(id) ON DELETE CASCADE
                    );
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rule_groups_rule_id
                    ON rule_groups(rule_id);
                """)

                # Check if group_id column exists on rule_conditions
                cur.execute("PRAGMA table_info(rule_conditions);")
                cols = {r["name"] for r in cur.fetchall()}
                if "group_id" not in cols:
                    conn.execute("ALTER TABLE rule_conditions ADD COLUMN group_id TEXT;")

                # Content extraction and OCR cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS file_content_index (
                        path TEXT PRIMARY KEY,
                        modified_at TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        content_text TEXT,
                        ocr_text TEXT,
                        indexed_at TEXT NOT NULL
                    );
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_content_index_path
                    ON file_content_index(path);
                """)

                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (2, datetime('now'));"
                )
