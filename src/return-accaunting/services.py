"""Сервисный слой: бизнес-логика, проверки и обработка ошибок.

UI-слой обращается только к сервисам и не работает с SQL напрямую.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

from models import (
    ROLE_CASHIER,
    ROLE_MANAGER,
    STATUS_DONE,
    STATUS_NEW,
    STATUS_REJECTED,
    STATUSES,
    Product,
    Return,
    ReturnItem,
    User,
)
from repositories import (
    ProductRepository,
    ReturnItemRepository,
    ReturnRepository,
    SaleItemRepository,
    SaleRepository,
    UserRepository,
    UserRoleRepository,
)

RETURN_PERIOD_DAYS = 14   # срок, в течение которого возможен возврат
MIN_PASSWORD_LEN = 4
MANAGER_CODE = "manager2026"  # код для самостоятельной регистрации менеджера


class ServiceError(Exception):
    """Базовая ошибка бизнес-логики."""


class ValidationError(ServiceError):
    """Некорректные данные."""


class NotFoundError(ServiceError):
    """Объект не найден."""


class AuthError(ServiceError):
    """Ошибка авторизации или регистрации."""


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Авторизация и регистрация
# ---------------------------------------------------------------------------

class AuthService:
    def __init__(self, conn: sqlite3.Connection,
                 users: UserRepository, roles: UserRoleRepository):
        self.conn = conn
        self.users = users
        self.roles = roles

    def authenticate(self, login: str, password: str) -> User:
        user = self.users.get_by_login(login.strip())
        if user is None or user.password_hash != hash_password(password):
            raise AuthError("Неверный логин или пароль")
        return user

    def get_role_name(self, user: User) -> str:
        role = self.roles.get_by_id(user.role_id)
        return role.name if role else ""

    def register_manager(self, surname: str, name: str, patronymic: str,
                         login: str, password: str, code: str) -> User:
        if code != MANAGER_CODE:
            raise AuthError("Неверный код менеджера")
        return self._register(surname, name, patronymic, login, password,
                              ROLE_MANAGER)

    def register_cashier(self, surname: str, name: str, patronymic: str,
                         login: str, password: str) -> User:
        return self._register(surname, name, patronymic, login, password,
                              ROLE_CASHIER)

    def list_cashiers(self) -> list[User]:
        role = self.roles.get_by_name(ROLE_CASHIER)
        return self.users.get_by_role(role.role_id) if role else []

    def _register(self, surname: str, name: str, patronymic: str,
                  login: str, password: str, role_name: str) -> User:
        surname, name, login = surname.strip(), name.strip(), login.strip()
        patronymic = patronymic.strip() or None

        if not surname or not name or not login:
            raise ValidationError("Фамилия, имя и логин обязательны")
        if len(password) < MIN_PASSWORD_LEN:
            raise ValidationError(
                f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов")
        if self.users.get_by_login(login) is not None:
            raise ValidationError("Пользователь с таким логином уже существует")

        role = self.roles.get_by_name(role_name)
        if role is None:
            raise NotFoundError(f"Роль «{role_name}» не найдена")

        user = User(surname=surname, name=name, patronymic=patronymic,
                    login=login, password_hash=hash_password(password),
                    role_id=role.role_id)
        try:
            self.users.add(user)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return user


# ---------------------------------------------------------------------------
# Товары
# ---------------------------------------------------------------------------

class ProductService:
    def __init__(self, conn: sqlite3.Connection, products: ProductRepository):
        self.conn = conn
        self.products = products

    def list_products(self) -> list[Product]:
        return self.products.get_all()

    def set_stock(self, product_id: int, new_qty: int) -> Product:
        if new_qty < 0:
            raise ValidationError("Остаток не может быть отрицательным")
        product = self.products.get_by_id(product_id)
        if product is None:
            raise NotFoundError("Товар не найден")
        product.stock_qty = new_qty
        try:
            self.products.update(product)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return product


# ---------------------------------------------------------------------------
# Продажи
# ---------------------------------------------------------------------------

class SaleService:
    def __init__(self, sales: SaleRepository, sale_items: SaleItemRepository,
                 products: ProductRepository,
                 return_items: ReturnItemRepository):
        self.sales = sales
        self.sale_items = sale_items
        self.products = products
        self.return_items = return_items

    def get_sale_details(self, receipt_number: str) -> dict:
        """Чек и его позиции с количеством, доступным для возврата."""
        receipt_number = receipt_number.strip()
        if not receipt_number:
            raise ValidationError("Введите номер чека")
        sale = self.sales.get_by_receipt(receipt_number)
        if sale is None:
            raise NotFoundError("Продажа (чек) не найдена")

        items = []
        for sale_item in self.sale_items.get_by_sale(sale.sale_id):
            product = self.products.get_by_id(sale_item.product_id)
            returned = self.return_items.get_returned_quantity(
                sale_item.sale_item_id)
            items.append({
                "sale_item": sale_item,
                "product_name": product.name if product else "?",
                "available": sale_item.quantity - returned,
            })
        return {"sale": sale, "items": items}


# ---------------------------------------------------------------------------
# Возвраты
# ---------------------------------------------------------------------------

class ReturnService:
    def __init__(self, conn: sqlite3.Connection, returns: ReturnRepository,
                 return_items: ReturnItemRepository, sales: SaleRepository,
                 sale_items: SaleItemRepository, products: ProductRepository):
        self.conn = conn
        self.returns = returns
        self.return_items = return_items
        self.sales = sales
        self.sale_items = sale_items
        self.products = products

    # --- оформление возврата кассиром ---------------------------------

    def create_return(self, cashier_id: int, receipt_number: str, reason: str,
                      items: dict[int, int]) -> Return:
        """items: {id позиции чека: количество к возврату}."""
        reason = reason.strip()
        if not receipt_number.strip():
            raise ValidationError("Введите номер чека")
        if not reason:
            raise ValidationError("Укажите причину возврата")
        if not items:
            raise ValidationError("Выберите хотя бы одну позицию для возврата")

        sale = self.sales.get_by_receipt(receipt_number.strip())
        if sale is None:
            raise NotFoundError("Продажа (чек) не найдена")

        days = (date.today() - date.fromisoformat(sale.sale_date)).days
        if days > RETURN_PERIOD_DAYS:
            raise ValidationError(
                f"Срок возврата истёк: с покупки прошло {days} дн., "
                f"допустимо {RETURN_PERIOD_DAYS}")

        for sale_item_id, quantity in items.items():
            sale_item = self.sale_items.get_by_id(sale_item_id)
            if sale_item is None or sale_item.sale_id != sale.sale_id:
                raise NotFoundError(
                    f"Позиция {sale_item_id} не относится к этому чеку")
            if quantity <= 0:
                raise ValidationError("Количество должно быть больше нуля")
            returned = self.return_items.get_returned_quantity(sale_item_id)
            available = sale_item.quantity - returned
            if quantity > available:
                raise ValidationError(
                    f"Позиция {sale_item_id}: можно вернуть не более "
                    f"{available} шт.")

        try:
            new_return = self.returns.add(Return(
                sale_id=sale.sale_id,
                cashier_id=cashier_id,
                return_date=date.today().isoformat(),
                reason=reason,
                status=STATUS_NEW,
            ))
            for sale_item_id, quantity in items.items():
                self.return_items.add(ReturnItem(
                    return_id=new_return.return_id,
                    sale_item_id=sale_item_id,
                    quantity=quantity,
                ))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return new_return

    # --- просмотр -----------------------------------------------------

    def list_returns(self, status: Optional[str] = None,
                     cashier_id: Optional[int] = None) -> list[Return]:
        if cashier_id is not None:
            returns = self.returns.get_by_cashier(cashier_id)
        elif status is not None:
            returns = self.returns.get_by_status(status)
        else:
            returns = self.returns.get_all()
        if status is not None and cashier_id is not None:
            returns = [r for r in returns if r.status == status]
        return returns

    def get_details(self, return_id: int) -> dict:
        ret = self.returns.get_by_id(return_id)
        if ret is None:
            raise NotFoundError("Возврат не найден")
        sale = self.sales.get_by_id(ret.sale_id)
        entries = []
        for item in self.return_items.get_by_return(return_id):
            sale_item = self.sale_items.get_by_id(item.sale_item_id)
            product = self.products.get_by_id(sale_item.product_id)
            entries.append({
                "item": item,
                "product_name": product.name if product else "?",
                "price": sale_item.price,
            })
        return {
            "return": ret,
            "receipt_number": sale.receipt_number if sale else "?",
            "items": entries,
        }

    # --- обработка возврата менеджером --------------------------------

    def process_return(self, manager_id: int, return_id: int,
                       decisions: dict[int, tuple[bool, bool]]) -> Return:
        """decisions: {id позиции возврата: (в надлежащем состоянии, вернуть в продажу)}.

        Если хотя бы один товар в ненадлежащем состоянии — возврат отклоняется.
        Иначе: при «вернуть в продажу» остаток на складе увеличивается,
        иначе товар списывается; считается сумма возврата, статус «Выполнен».
        """
        ret = self.returns.get_by_id(return_id)
        if ret is None:
            raise NotFoundError("Возврат не найден")
        if ret.status != STATUS_NEW:
            raise ValidationError(
                f"Возврат уже обработан (статус «{ret.status}»)")

        items = self.return_items.get_by_return(return_id)
        for item in items:
            if item.return_item_id not in decisions:
                raise ValidationError(
                    "Нужно принять решение по каждой позиции возврата")

        all_good = all(decisions[i.return_item_id][0] for i in items)

        try:
            refund = 0.0
            for item in items:
                is_good, restock = decisions[item.return_item_id]
                item.is_good_condition = 1 if is_good else 0
                item.restock = 1 if (all_good and restock) else 0

                if all_good:
                    sale_item = self.sale_items.get_by_id(item.sale_item_id)
                    refund += sale_item.price * item.quantity
                    if restock:
                        product = self.products.get_by_id(sale_item.product_id)
                        product.stock_qty += item.quantity
                        self.products.update(product)
                self.return_items.update(item)

            ret.manager_id = manager_id
            if all_good:
                ret.status = STATUS_DONE
                ret.refund_amount = refund
            else:
                ret.status = STATUS_REJECTED
                ret.refund_amount = 0.0
            self.returns.update(ret)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return ret

    # --- отчёт --------------------------------------------------------

    def report(self) -> dict:
        returns = self.returns.get_all()
        by_status = {status: 0 for status in STATUSES}
        refund_sum = 0.0
        for ret in returns:
            by_status[ret.status] = by_status.get(ret.status, 0) + 1
            if ret.status == STATUS_DONE:
                refund_sum += ret.refund_amount or 0.0
        return {
            "total": len(returns),
            "by_status": by_status,
            "refund_sum": refund_sum,
        }


# ---------------------------------------------------------------------------
# Сборка всех сервисов
# ---------------------------------------------------------------------------

@dataclass
class Services:
    auth: AuthService
    products: ProductService
    sales: SaleService
    returns: ReturnService


def build_services(conn: sqlite3.Connection) -> Services:
    roles = UserRoleRepository(conn)
    users = UserRepository(conn)
    products = ProductRepository(conn)
    sales = SaleRepository(conn)
    sale_items = SaleItemRepository(conn)
    returns = ReturnRepository(conn)
    return_items = ReturnItemRepository(conn)

    return Services(
        auth=AuthService(conn, users, roles),
        products=ProductService(conn, products),
        sales=SaleService(sales, sale_items, products, return_items),
        returns=ReturnService(conn, returns, return_items, sales,
                              sale_items, products),
    )
