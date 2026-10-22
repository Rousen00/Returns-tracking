"""Консольный интерфейс. Работает только с сервисами, SQL здесь нет."""

import auth
from inputs import ask_int, ask_text, ask_yes_no, print_menu
from models import ROLE_CASHIER, ROLE_MANAGER, STATUS_NEW, User
from services import ServiceError, Services


# ---------------------------------------------------------------------------
# Вывод данных
# ---------------------------------------------------------------------------

def print_returns_table(returns) -> None:
    if not returns:
        print("Возвратов нет.")
        return
    print(f"{'ID':<4}{'Дата':<12}{'Статус':<10}{'Сумма':>10}  Причина")
    for ret in returns:
        amount = f"{ret.refund_amount:.2f}" if ret.refund_amount is not None else "-"
        print(f"{ret.return_id:<4}{ret.return_date:<12}{ret.status:<10}"
              f"{amount:>10}  {ret.reason}")


def print_return_details(details: dict) -> None:
    ret = details["return"]
    print(f"\nВозврат №{ret.return_id} по чеку {details['receipt_number']}")
    print(f"Дата: {ret.return_date}   Статус: {ret.status}")
    print(f"Причина: {ret.reason}")
    if ret.refund_amount is not None:
        print(f"Сумма возврата: {ret.refund_amount:.2f}")
    print("Позиции:")
    for entry in details["items"]:
        item = entry["item"]
        print(f"  - {entry['product_name']}: {item.quantity} шт. "
              f"по {entry['price']:.2f}")


# ---------------------------------------------------------------------------
# Меню кассира
# ---------------------------------------------------------------------------

def create_return_flow(services: Services, user: User) -> None:
    receipt = ask_text("Номер чека (например, CHK-0001): ")
    details = services.sales.get_sale_details(receipt)

    print(f"\nЧек {details['sale'].receipt_number} от {details['sale'].sale_date}")
    print(f"{'ID':<4}{'Товар':<20}{'Куплено':>8}{'Можно вернуть':>15}")
    for entry in details["items"]:
        sale_item = entry["sale_item"]
        print(f"{sale_item.sale_item_id:<4}{entry['product_name']:<20}"
              f"{sale_item.quantity:>8}{entry['available']:>15}")

    items: dict[int, int] = {}
    print("\nВведите ID позиции и количество. Пустой ввод ID — закончить.")
    while True:
        raw = input("ID позиции: ").strip()
        if not raw:
            break
        if not raw.isdigit():
            print("Введите число.")
            continue
        quantity = ask_int("Количество к возврату: ", min_value=1)
        items[int(raw)] = quantity

    reason = ask_text("Причина возврата: ")
    new_return = services.returns.create_return(
        user.user_id, receipt, reason, items)
    print(f"Возврат №{new_return.return_id} зарегистрирован "
          f"со статусом «{new_return.status}».")


def cashier_menu(services: Services, user: User) -> None:
    while True:
        print_menu("Меню кассира", ["Оформить возврат", "Мои возвраты"])
        choice = input("Выберите пункт: ").strip()
        try:
            if choice == "1":
                create_return_flow(services, user)
            elif choice == "2":
                print_returns_table(
                    services.returns.list_returns(cashier_id=user.user_id))
            elif choice == "0":
                break
            else:
                print("Нет такого пункта меню.")
        except ServiceError as error:
            print(f"Ошибка: {error}")


# ---------------------------------------------------------------------------
# Меню менеджера
# ---------------------------------------------------------------------------

def process_return_flow(services: Services, user: User) -> None:
    new_returns = services.returns.list_returns(status=STATUS_NEW)
    if not new_returns:
        print("Новых возвратов нет.")
        return
    print("\nНовые возвраты:")
    print_returns_table(new_returns)

    return_id = ask_int("ID возврата для обработки (0 — отмена): ", min_value=0)
    if return_id == 0:
        return

    details = services.returns.get_details(return_id)
    print_return_details(details)

    decisions: dict[int, list[bool]] = {}
    for entry in details["items"]:
        good = ask_yes_no(f"Товар «{entry['product_name']}» "
                          f"в надлежащем состоянии?")
        decisions[entry["item"].return_item_id] = [good, False]

    if all(good for good, _ in decisions.values()):
        for entry in details["items"]:
            resale = ask_yes_no(f"Товар «{entry['product_name']}» "
                                f"можно вернуть в продажу?")
            decisions[entry["item"].return_item_id][1] = resale

    result = services.returns.process_return(
        user.user_id, return_id,
        {key: (value[0], value[1]) for key, value in decisions.items()})

    if result.status == "Отклонён":
        print(f"Возврат №{result.return_id} отклонён: товар в ненадлежащем состоянии.")
    else:
        print(f"Возврат №{result.return_id} выполнен. "
              f"Сумма возврата: {result.refund_amount:.2f}")


def stock_flow(services: Services) -> None:
    products = services.products.list_products()
    print(f"\n{'ID':<4}{'Товар':<20}{'Цена':>10}{'Остаток':>10}")
    for product in products:
        print(f"{product.product_id:<4}{product.name:<20}"
              f"{product.price:>10.2f}{product.stock_qty:>10}")

    if not ask_yes_no("Изменить остаток товара?"):
        return
    product_id = ask_int("ID товара: ", min_value=1)
    new_qty = ask_int("Новый остаток: ", min_value=0)
    product = services.products.set_stock(product_id, new_qty)
    print(f"Остаток товара «{product.name}» теперь {product.stock_qty}.")


def report_flow(services: Services) -> None:
    report = services.returns.report()
    print("\n--- Отчёт по возвратам ---")
    print(f"Всего возвратов: {report['total']}")
    for status, count in report["by_status"].items():
        print(f"  {status}: {count}")
    print(f"Возвращено денег по выполненным: {report['refund_sum']:.2f}")


def manager_menu(services: Services, user: User) -> None:
    while True:
        print_menu("Меню менеджера", [
            "Обработать новый возврат",
            "Список всех возвратов",
            "Отчёт по возвратам",
            "Товары и остатки",
            "Зарегистрировать кассира",
        ])
        choice = input("Выберите пункт: ").strip()
        try:
            if choice == "1":
                process_return_flow(services, user)
            elif choice == "2":
                print_returns_table(services.returns.list_returns())
            elif choice == "3":
                report_flow(services)
            elif choice == "4":
                stock_flow(services)
            elif choice == "5":
                auth.add_cashier(services.auth)
            elif choice == "0":
                break
            else:
                print("Нет такого пункта меню.")
        except ServiceError as error:
            print(f"Ошибка: {error}")


# ---------------------------------------------------------------------------
# Стартовое меню
# ---------------------------------------------------------------------------

def run_app(services: Services) -> None:
    print("Система учёта возвратов товаров")
    while True:
        print_menu("Главное меню", ["Войти", "Зарегистрироваться (менеджер)"])
        choice = input("Выберите пункт: ").strip()

        if choice == "1":
            user = auth.login(services.auth)
            if user is None:
                continue
            role = services.auth.get_role_name(user)
            if role == ROLE_CASHIER:
                cashier_menu(services, user)
            elif role == ROLE_MANAGER:
                manager_menu(services, user)
            else:
                print("Для этой роли нет меню.")
        elif choice == "2":
            auth.register_manager(services.auth)
        elif choice == "0":
            print("До свидания!")
            break
        else:
            print("Нет такого пункта меню.")
