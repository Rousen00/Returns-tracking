import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "returns.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

TABLES = (
    "user_roles",
    "users",
    "products",
    "sales",
    "sale_items",
    "returns",
    "return_items",
)


def init_db():
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()

        for table in TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count} записей")
    finally:
        conn.close()

    print(f"База данных создана: {DB_PATH}")


if __name__ == "__main__":
    init_db()
