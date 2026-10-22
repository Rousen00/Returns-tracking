"""Репозитории: единственное место, где пишутся SQL-запросы.

Базовый класс даёт CRUD-операции для любой таблицы:
add (добавление), get_by_id / get_all (получение),
update (изменение), delete (удаление).
Транзакции (commit / rollback) выполняет сервисный слой.
"""

import sqlite3
from dataclasses import fields
from typing import Optional

from models import (
    Product,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    STATUS_REJECTED,
    User,
    UserRole,
)


class BaseRepository:
    table: str = ""
    pk: str = ""
    model: type = object

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # --- служебные методы ---------------------------------------------

    def _columns(self) -> list[str]:
        return [f.name for f in fields(self.model) if f.name != self.pk]

    def _to_model(self, row: sqlite3.Row):
        return self.model(**dict(row))

    def _fetch_one(self, sql: str, params: tuple = ()):
        row = self.conn.execute(sql, params).fetchone()
        return self._to_model(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> list:
        rows = self.conn.execute(sql, params).fetchall()
        return [self._to_model(row) for row in rows]

    # --- CRUD ---------------------------------------------------------

    def add(self, obj):
        columns = self._columns()
        values = [getattr(obj, column) for column in columns]
        placeholders = ", ".join("?" for _ in columns)
        cursor = self.conn.execute(
            f"INSERT INTO {self.table} ({', '.join(columns)}) "
            f"VALUES ({placeholders})",
            values,
        )
        setattr(obj, self.pk, cursor.lastrowid)
        return obj

    def get_by_id(self, object_id: int):
        return self._fetch_one(
            f"SELECT * FROM {self.table} WHERE {self.pk} = ?", (object_id,)
        )

    def get_all(self) -> list:
        return self._fetch_all(f"SELECT * FROM {self.table} ORDER BY {self.pk}")

    def update(self, obj) -> bool:
        columns = self._columns()
        assignments = ", ".join(f"{column} = ?" for column in columns)
        values = [getattr(obj, column) for column in columns]
        values.append(getattr(obj, self.pk))
        cursor = self.conn.execute(
            f"UPDATE {self.table} SET {assignments} WHERE {self.pk} = ?", values
        )
        return cursor.rowcount > 0

    def delete(self, object_id: int) -> bool:
        cursor = self.conn.execute(
            f"DELETE FROM {self.table} WHERE {self.pk} = ?", (object_id,)
        )
        return cursor.rowcount > 0


class UserRoleRepository(BaseRepository):
    table = "user_roles"
    pk = "role_id"
    model = UserRole

    def get_by_name(self, name: str) -> Optional[UserRole]:
        return self._fetch_one("SELECT * FROM user_roles WHERE name = ?", (name,))


class UserRepository(BaseRepository):
    table = "users"
    pk = "user_id"
    model = User

    def get_by_login(self, login: str) -> Optional[User]:
        return self._fetch_one("SELECT * FROM users WHERE login = ?", (login,))

    def get_by_role(self, role_id: int) -> list[User]:
        return self._fetch_all(
            "SELECT * FROM users WHERE role_id = ? ORDER BY user_id", (role_id,)
        )


class ProductRepository(BaseRepository):
    table = "products"
    pk = "product_id"
    model = Product


class SaleRepository(BaseRepository):
    table = "sales"
    pk = "sale_id"
    model = Sale

    def get_by_receipt(self, receipt_number: str) -> Optional[Sale]:
        return self._fetch_one(
            "SELECT * FROM sales WHERE receipt_number = ?", (receipt_number,)
        )


class SaleItemRepository(BaseRepository):
    table = "sale_items"
    pk = "sale_item_id"
    model = SaleItem

    def get_by_sale(self, sale_id: int) -> list[SaleItem]:
        return self._fetch_all(
            "SELECT * FROM sale_items WHERE sale_id = ? ORDER BY sale_item_id",
            (sale_id,),
        )


class ReturnRepository(BaseRepository):
    table = "returns"
    pk = "return_id"
    model = Return

    def get_by_status(self, status: str) -> list[Return]:
        return self._fetch_all(
            "SELECT * FROM returns WHERE status = ? ORDER BY return_id", (status,)
        )

    def get_by_cashier(self, cashier_id: int) -> list[Return]:
        return self._fetch_all(
            "SELECT * FROM returns WHERE cashier_id = ? ORDER BY return_id",
            (cashier_id,),
        )


class ReturnItemRepository(BaseRepository):
    table = "return_items"
    pk = "return_item_id"
    model = ReturnItem

    def get_by_return(self, return_id: int) -> list[ReturnItem]:
        return self._fetch_all(
            "SELECT * FROM return_items WHERE return_id = ? ORDER BY return_item_id",
            (return_id,),
        )

    def get_returned_quantity(self, sale_item_id: int) -> int:
        """Сколько единиц позиции чека уже оформлено к возврату (без отклонённых)."""
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(ri.quantity), 0)
            FROM return_items ri
            JOIN returns r ON r.return_id = ri.return_id
            WHERE ri.sale_item_id = ? AND r.status != ?
            """,
            (sale_item_id, STATUS_REJECTED),
        ).fetchone()
        return row[0]
