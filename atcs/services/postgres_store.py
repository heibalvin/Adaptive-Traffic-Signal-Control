"""
PostgreSQL persistence layer for Kafka events and device models.

Tables:
- traffic_lights: device metadata and current state
- traffic_light_events: audit log of all Kafka events
"""
import os
import logging
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

logger = logging.getLogger(__name__)


class PostgresConfig:
    def __init__(self):
        self.host = os.environ.get("POSTGRES_HOST", "aicd_postgres")
        self.user = os.environ.get("POSTGRES_USER", "postgres")
        self.password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        self.db = os.environ.get("POSTGRES_DB", "default")
        self.port = int(os.environ.get("POSTGRES_PORT", "5432"))

    @property
    def dsn(self) -> str:
        return f"host={self.host} user={self.user} password={self.password} dbname={self.db} port={self.port}"


class PostgresStore:
    """Persistence layer for traffic light devices and events."""

    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self._conn = None

    def connect(self):
        self._conn = psycopg2.connect(self.config.dsn)
        self._conn.autocommit = True
        self._ensure_schema()
        logger.info(f"PostgreSQL connected to {self.config.host}/{self.config.db}")

    def _ensure_schema(self):
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS traffic_lights (
                    id TEXT PRIMARY KEY,
                    green_timer INTEGER DEFAULT 50,
                    orange_timer INTEGER DEFAULT 5,
                    red_timer INTEGER DEFAULT 240,
                    state TEXT DEFAULT 'IDLE',
                    colour TEXT DEFAULT 'RED',
                    updated_at DOUBLE PRECISION DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS traffic_light_events (
                    id SERIAL PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload JSONB,
                    timestamp DOUBLE PRECISION,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_device ON traffic_light_events(device_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON traffic_light_events(timestamp)
            """)

    def save_device(self, device_dict: dict):
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO traffic_lights (id, green_timer, orange_timer, red_timer, state, colour, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    green_timer = EXCLUDED.green_timer,
                    orange_timer = EXCLUDED.orange_timer,
                    red_timer = EXCLUDED.red_timer,
                    state = EXCLUDED.state,
                    colour = EXCLUDED.colour,
                    updated_at = EXCLUDED.updated_at
            """, (
                device_dict["id"],
                device_dict.get("greenTimer", 50),
                device_dict.get("orangeTimer", 5),
                device_dict.get("redTimer", 240),
                device_dict.get("state", "IDLE"),
                device_dict.get("colour", "RED"),
                device_dict.get("updated_at", 0),
            ))

    def save_event(self, event: dict):
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO traffic_light_events (device_id, event_type, payload, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (
                event.get("device_id", event.get("id")),
                event.get("type"),
                event.get("payload", event),
                event.get("timestamp", 0),
            ))

    def get_all_devices(self) -> list[dict]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM traffic_lights ORDER BY updated_at DESC")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_device(self, device_id: str) -> Optional[dict]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM traffic_lights WHERE id = %s", (device_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_device(self, device_id: str):
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM traffic_lights WHERE id = %s", (device_id,))
            cur.execute("DELETE FROM traffic_light_events WHERE device_id = %s", (device_id,))

    def get_events(self, device_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if device_id:
                cur.execute(
                    "SELECT * FROM traffic_light_events WHERE device_id = %s ORDER BY timestamp DESC LIMIT %s",
                    (device_id, limit)
                )
            else:
                cur.execute(
                    "SELECT * FROM traffic_light_events ORDER BY timestamp DESC LIMIT %s",
                    (limit,)
                )
            return [dict(r) for r in cur.fetchall()]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None