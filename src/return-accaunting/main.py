import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "db"))

from database import DB_PATH, get_connection
from init_db import init_db
from services import build_services
from ui import run_app


def main() -> None:
    if not DB_PATH.exists():
        init_db()

    conn = get_connection()
    try:
        run_app(build_services(conn))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
