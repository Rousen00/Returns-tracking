"""Экспорт записей SQLite в JSON, CSV, XML и YAML."""

import argparse
import csv
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from xml.etree import ElementTree as ET

from init_db import DB_PATH


OUT_DIR = Path(__file__).resolve().parents[2] / "out"
# Точка в псевдониме SQL обозначает путь к полю вложенного объекта.
QUERY = """
SELECT r.return_id, r.sale_id, r.cashier_id, r.manager_id,
       r.return_date, r.reason, r.status, r.refund_amount,
       s.sale_id AS "sale.sale_id",
       s.receipt_number AS "sale.receipt_number",
       s.sale_date AS "sale.sale_date",
       c.user_id AS "cashier.user_id",
       c.surname AS "cashier.surname",
       c.name AS "cashier.name",
       c.patronymic AS "cashier.patronymic",
       m.user_id AS "manager.user_id",
       m.surname AS "manager.surname",
       m.name AS "manager.name",
       m.patronymic AS "manager.patronymic"
FROM returns AS r
LEFT JOIN sales AS s ON s.sale_id = r.sale_id
LEFT JOIN users AS c ON c.user_id = r.cashier_id
LEFT JOIN users AS m ON m.user_id = r.manager_id
ORDER BY r.return_id
"""
XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI)


def nest_row(columns, row):
    record = {}
    for column, value in zip(columns, row):
        *parents, key = column.split(".")
        target = record
        for parent in parents:
            target = target.setdefault(parent, {})
        target[key] = value
    return collapse_missing_objects(record)


def collapse_missing_objects(record):
    for key, value in record.items():
        if isinstance(value, dict):
            record[key] = collapse_missing_objects(value)
            if all(field is None for field in value.values()):
                record[key] = None
    return record


def write_xml_fields(parent, record):
    for name, value in record.items():
        element = ET.SubElement(parent, name)
        if isinstance(value, dict):
            write_xml_fields(element, value)
        elif value is None:
            element.set(f"{{{XSI}}}nil", "true")
        else:
            element.text = str(value)


def yaml_fields(record, indent=0):
    """Формирует строки YAML для словаря со значениями SQLite."""
    prefix = " " * indent
    for key, value in record.items():
        name = yaml_scalar(key)
        if isinstance(value, dict):
            yield f"{prefix}{name}:"
            yield from yaml_fields(value, indent + 2)
        else:
            yield f"{prefix}{name}: {yaml_scalar(value)}"


def yaml_scalar(value):
    # Кавычки сохраняют строковый тип у дат, чисел и других похожих значений.
    literal = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, float) and "e" in literal:
        mantissa, exponent = literal.split("e")
        if "." not in mantissa:
            literal = f"{mantissa}.0e{exponent}"
    return literal.replace("\x85", r"\u0085").replace("\u2028", r"\u2028").replace(
        "\u2029", r"\u2029"
    )


def write_yaml(file, records):
    if not records:
        file.write("[]\n")
    for record in records:
        fields = iter(yaml_fields(record, indent=2))
        file.write("- " + next(fields).lstrip() + "\n")
        for line in fields:
            file.write(line + "\n")


def export_data(db_path, out_dir, query=QUERY, root_tag="returns", item_tag="return"):
    database_uri = db_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        cursor = connection.execute(query)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

    records = [nest_row(columns, row) for row in rows]
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "data.json").open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")

    with (out_dir / "data.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)

    root = ET.Element(root_tag)
    for record in records:
        write_xml_fields(ET.SubElement(root, item_tag), record)
    ET.indent(root)
    ET.ElementTree(root).write(out_dir / "data.xml", encoding="utf-8", xml_declaration=True)

    with (out_dir / "data.yaml").open("w", encoding="utf-8") as file:
        write_yaml(file, records)

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="путь к файлу SQLite")
    args = parser.parse_args()
    try:
        count = export_data(args.db, OUT_DIR)
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"Ошибка экспорта ({args.db}): {error}\n")
    print(f"Экспортировано записей: {count}. Результаты: {OUT_DIR}")


if __name__ == "__main__":
    main()
