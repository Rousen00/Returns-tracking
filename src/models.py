"""Модели данных: по одному dataclass на каждую таблицу базы данных."""

from dataclasses import dataclass
from typing import Optional

ROLE_CASHIER = "Кассир"
ROLE_MANAGER = "Менеджер"

STATUS_NEW = "Новый"
STATUS_DONE = "Выполнен"
STATUS_REJECTED = "Отклонён"
STATUSES = (STATUS_NEW, STATUS_DONE, STATUS_REJECTED)


@dataclass(kw_only=True)
class UserRole:
    role_id: Optional[int] = None
    name: str


@dataclass(kw_only=True)
class User:
    user_id: Optional[int] = None
    surname: str
    name: str
    patronymic: Optional[str] = None
    login: str
    password_hash: str
    role_id: int

    @property
    def full_name(self) -> str:
        parts = [self.surname, self.name, self.patronymic]
        return " ".join(part for part in parts if part)


@dataclass(kw_only=True)
class Product:
    product_id: Optional[int] = None
    name: str
    price: float
    stock_qty: int


@dataclass(kw_only=True)
class Sale:
    sale_id: Optional[int] = None
    receipt_number: str
    sale_date: str
    cashier_id: int


@dataclass(kw_only=True)
class SaleItem:
    sale_item_id: Optional[int] = None
    sale_id: int
    product_id: int
    quantity: int
    price: float


@dataclass(kw_only=True)
class Return:
    return_id: Optional[int] = None
    sale_id: int
    cashier_id: int
    manager_id: Optional[int] = None
    return_date: str
    reason: str
    status: str = STATUS_NEW
    refund_amount: Optional[float] = None


@dataclass(kw_only=True)
class ReturnItem:
    return_item_id: Optional[int] = None
    return_id: int
    sale_item_id: int
    quantity: int
    is_good_condition: Optional[int] = None
    restock: Optional[int] = None
