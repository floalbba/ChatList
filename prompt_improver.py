"""AI-ассистент для улучшения промтов."""

import re
from typing import Optional

import network


SYSTEM_PROMPT = """Ты — эксперт по формулировке промтов для нейросетей. Твоя задача — улучшать и переформулировать запросы пользователей.

Ответь СТРОГО в следующем формате (сохраняй заголовки):

## Улучшенный
[улучшенная версия промта — более чёткая, структурированная, без лишних слов]

## Вариант 1
[первая переформулировка]

## Вариант 2
[вторая переформулировка]

## Вариант 3
[третья переформулировка]

## Код
[адаптация промта для задач программирования и генерации кода]

## Анализ
[адаптация для аналитических задач, сравнения, выводов]

## Креатив
[адаптация для креативных задач: тексты, идеи, стили]

Каждый блок — отдельный промт. Пиши только текст промта, без пояснений."""


def build_improvement_prompt(original_prompt: str, mode: str = "full") -> list[dict]:
    """
    Формирует список сообщений для модели.
    mode: full (всё), improve, variants, adapt
    """
    system = SYSTEM_PROMPT
    user = f"Исходный промт пользователя:\n\n{original_prompt}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_improvement_response(text: str) -> dict:
    """Парсит ответ модели в структурированный формат."""
    result = {
        "improved": "",
        "variants": [],
        "adapted": {"code": "", "analysis": "", "creative": ""},
    }
    if not text or not text.strip():
        return result

    # Разбиваем по заголовкам ## 
    sections = re.split(r"\n##\s+", text, flags=re.IGNORECASE)
    improved_done = False

    for part in sections:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n")
        title = lines[0].strip().lower()
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        if "улучшен" in title and not improved_done:
            result["improved"] = content
            improved_done = True
        elif "вариант 1" in title or "вариант 2" in title or "вариант 3" in title:
            result["variants"].append(content)
        elif "код" in title:
            result["adapted"]["code"] = content
        elif "анализ" in title:
            result["adapted"]["analysis"] = content
        elif "креатив" in title:
            result["adapted"]["creative"] = content

    # Если парсинг не сработал — весь текст как improved
    if not result["improved"] and not result["variants"]:
        result["improved"] = text.strip()

    return result


def improve_prompt(
    original: str,
    model: dict,
    timeout: float = 60.0
) -> tuple[dict, Optional[str]]:
    """
    Улучшает промт через указанную модель.
    Возвращает (result, error).
    result: {improved, variants, adapted: {code, analysis, creative}}
    """
    messages = build_improvement_prompt(original)
    response_text, error = network.send_prompt_with_messages(model, messages, timeout)
    if error:
        return (
            {"improved": "", "variants": [], "adapted": {"code": "", "analysis": "", "creative": ""}},
            error,
        )
    return _parse_improvement_response(response_text), None
