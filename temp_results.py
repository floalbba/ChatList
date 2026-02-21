"""Временная таблица результатов в памяти. Не сохраняется в SQLite."""

from typing import Optional

import db


# Список строк: каждая — dict с model_name, response, selected, model_id
_temp_results: list[dict] = []

# ID текущего промта (для сохранения в results)
_current_prompt_id: Optional[int] = None


def clear() -> None:
    """Очищает временную таблицу (при новом запросе)."""
    global _temp_results, _current_prompt_id
    _temp_results = []
    _current_prompt_id = None


def set_prompt_id(prompt_id: int) -> None:
    """Устанавливает id промта для последующего сохранения."""
    global _current_prompt_id
    _current_prompt_id = prompt_id


def add_result(model_id: int, model_name: str, response: str, selected: bool = False) -> None:
    """Добавляет строку в временную таблицу."""
    _temp_results.append({
        "model_id": model_id,
        "model_name": model_name,
        "response": response,
        "selected": selected,
    })


def fill_from_network_results(network_results: list[dict]) -> None:
    """
    Заполняет временную таблицу из результатов network.send_prompt_to_models.
    network_results: [{"model": dict, "response": str, "error": str|None}, ...]
    """
    for item in network_results:
        model = item["model"]
        response = item["response"] if item["error"] is None else f"Ошибка: {item['error']}"
        add_result(
            model_id=model["id"],
            model_name=model["name"],
            response=response,
            selected=False,
        )


def get_all() -> list[dict]:
    """Возвращает все строки временной таблицы."""
    return list(_temp_results)


def set_selected(index: int, selected: bool) -> None:
    """Устанавливает флаг selected для строки по индексу."""
    if 0 <= index < len(_temp_results):
        _temp_results[index]["selected"] = selected


def get_selected() -> list[dict]:
    """Возвращает только строки с selected=True."""
    return [r for r in _temp_results if r["selected"]]


def save_selected_to_db() -> int:
    """
    Сохраняет выбранные строки (selected=True) в таблицу results.
    Возвращает количество сохранённых записей.
    Очищает временную таблицу после сохранения.
    """
    global _temp_results, _current_prompt_id

    if _current_prompt_id is None:
        return 0

    count = 0
    for row in _temp_results:
        if row["selected"]:
            db.create_result(
                prompt_id=_current_prompt_id,
                model_id=row["model_id"],
                model_name=row["model_name"],
                response=row["response"],
            )
            count += 1

    clear()
    return count


def has_data() -> bool:
    """Проверяет, есть ли данные во временной таблице."""
    return len(_temp_results) > 0
