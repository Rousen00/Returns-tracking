"""Вспомогательные функции консольного ввода с проверкой."""

from typing import Optional


def ask_text(prompt: str, allow_empty: bool = False) -> str:
    while True:
        value = input(prompt).strip()
        if value or allow_empty:
            return value
        print("Поле не может быть пустым.")


def ask_int(prompt: str, min_value: Optional[int] = None) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Введите целое число.")
            continue
        if min_value is not None and value < min_value:
            print(f"Число должно быть не меньше {min_value}.")
            continue
        return value


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} (д/н): ").strip().lower()
        if answer in ("д", "да", "y", "yes"):
            return True
        if answer in ("н", "нет", "n", "no"):
            return False
        print("Ответьте «д» или «н».")


def print_menu(title: str, items: list[str]) -> None:
    print(f"\n=== {title} ===")
    for number, text in enumerate(items, start=1):
        print(f"{number}. {text}")
    print("0. Назад / выход")
