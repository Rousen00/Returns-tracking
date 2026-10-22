"""Авторизация и регистрация пользователей (консольные диалоги)."""

from getpass import getpass
from typing import Optional

from inputs import ask_text
from models import User
from services import AuthError, AuthService, ServiceError


def _read_password(prompt: str) -> str:
    """Пароль скрывается при вводе; если консоль не поддерживает — обычный ввод."""
    return input(prompt)


def login(auth: AuthService) -> Optional[User]:
    login_value = ask_text("Логин: ")
    password_value = _read_password("Пароль: ")
    try:
        user = auth.authenticate(login_value, password_value)
    except AuthError as error:
        print(error)
        return None
    print(f"\nДобро пожаловать, {user.full_name}! Роль: {auth.get_role_name(user)}")
    return user


def register_manager(auth: AuthService) -> None:
    """Самостоятельная регистрация менеджера (по коду доступа)."""
    print("\n--- Регистрация менеджера ---")
    surname = ask_text("Фамилия: ")
    name = ask_text("Имя: ")
    patronymic = ask_text("Отчество (можно пропустить): ", allow_empty=True)
    login_value = ask_text("Логин: ")
    password_value = _read_password("Пароль: ")
    code = _read_password("Код менеджера: ")
    try:
        user = auth.register_manager(surname, name, patronymic,
                                     login_value, password_value, code)
    except ServiceError as error:
        print(f"Ошибка: {error}")
        return
    print(f"Менеджер {user.full_name} зарегистрирован. Теперь можно войти.")


def add_cashier(auth: AuthService) -> None:
    """Регистрация кассира (доступна менеджеру)."""
    print("\n--- Регистрация кассира ---")
    surname = ask_text("Фамилия: ")
    name = ask_text("Имя: ")
    patronymic = ask_text("Отчество (можно пропустить): ", allow_empty=True)
    login_value = ask_text("Логин: ")
    password_value = _read_password("Пароль: ")
    try:
        user = auth.register_cashier(surname, name, patronymic,
                                     login_value, password_value)
    except ServiceError as error:
        print(f"Ошибка: {error}")
        return
    print(f"Кассир {user.full_name} зарегистрирован.")
