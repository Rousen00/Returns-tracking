import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "returns.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS user_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    surname       TEXT NOT NULL,
    name          TEXT NOT NULL,
    patronymic    TEXT,
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id       INTEGER NOT NULL,
    FOREIGN KEY (role_id) REFERENCES user_roles(role_id)
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    price      REAL NOT NULL CHECK (price >= 0),
    stock_qty  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number TEXT NOT NULL UNIQUE,
    sale_date      TEXT NOT NULL,
    cashier_id     INTEGER NOT NULL,
    FOREIGN KEY (cashier_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id      INTEGER NOT NULL,
    product_id   INTEGER NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    price        REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS returns (
    return_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id       INTEGER NOT NULL,
    cashier_id    INTEGER NOT NULL,
    manager_id    INTEGER,
    return_date   TEXT NOT NULL,
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Новый'
                  CHECK (status IN ('Новый', 'Выполнен', 'Отклонён')),
    refund_amount REAL,
    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    FOREIGN KEY (cashier_id) REFERENCES users(user_id),
    FOREIGN KEY (manager_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS return_items (
    return_item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id         INTEGER NOT NULL,
    sale_item_id      INTEGER NOT NULL,
    quantity          INTEGER NOT NULL CHECK (quantity > 0),
    is_good_condition INTEGER,
    restock           INTEGER,
    FOREIGN KEY (return_id) REFERENCES returns(return_id),
    FOREIGN KEY (sale_item_id) REFERENCES sale_items(sale_item_id)
);
"""

DATA = """
INSERT INTO user_roles (name) VALUES
    ('Кассир'),
    ('Менеджер');

INSERT INTO users (surname, name, patronymic, login, password_hash, role_id) VALUES
    ('Иванова', 'Анна', 'Сергеевна', 'ivanova', 'hash_1234', 1),
    ('Петров', 'Олег', 'Иванович', 'petrov', 'hash_1234', 1),
    ('Смирнов', 'Павел', 'Андреевич', 'smirnov', 'hash_admin', 2);

INSERT INTO products (name, price, stock_qty) VALUES
    ('Кроссовки', 4500.00, 10),
    ('Футболка', 1200.00, 25),
    ('Рюкзак', 3200.00, 7);

INSERT INTO sales (receipt_number, sale_date, cashier_id) VALUES
    ('CHK-0001', '2026-10-01', 1),
    ('CHK-0002', '2026-10-03', 2);

INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES
    (1, 1, 1, 4500.00),
    (1, 2, 2, 1200.00),
    (2, 3, 1, 3200.00);

INSERT INTO returns (sale_id, cashier_id, manager_id, return_date, reason, status, refund_amount) VALUES
    (1, 1, 3, '2026-10-05', 'Не подошёл размер', 'Выполнен', 4500.00),
    (2, 2, NULL, '2026-10-06', 'Брак: порвана молния', 'Новый', NULL);

INSERT INTO return_items (return_id, sale_item_id, quantity, is_good_condition, restock) VALUES
    (1, 1, 1, 1, 1),
    (2, 3, 1, 0, 0);
"""

TABLES = (
    "user_roles",
    "users",
    "products",
    "sales",
    "sale_items",
    "returns",
    "return_items",
)


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.executescript(DATA)
        conn.commit()

        for table in TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count} записей")
    finally:
        conn.close()

    print(f"База данных создана: {DB_PATH}")


if __name__ == "__main__":
    main()