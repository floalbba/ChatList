"""Модуль отправки HTTP-запросов к API нейросетей."""

import logging
import time
import httpx
from typing import Optional

from models import get_api_key, build_request_body, get_auth_header

try:
    from log_requests import log_request
except ImportError:
    def log_request(*args, **kwargs):
        pass

log = logging.getLogger(__name__)


class NetworkError(Exception):
    """Ошибка при отправке запроса."""
    pass


def send_prompt_to_model(
    model: dict,
    prompt: str,
    timeout: float = 60.0
) -> tuple[str, Optional[str]]:
    """
    Отправляет промт в одну модель.
    model: dict с полями name, api_url, api_id, model_type
    Возвращает (response_text, error_message).
    error_message = None при успехе.
    """
    api_key = get_api_key(model["api_id"])
    if not api_key:
        log_request(model.get("name", ""), prompt, "", "API-ключ не найден")
        return "", "API-ключ не найден. Добавьте переменную в .env"

    body = build_request_body(
        model.get("model_type", "openai"),
        prompt,
        model.get("name", "")
    )

    header_name, header_value = get_auth_header(model["api_id"])
    headers = {
        "Content-Type": "application/json",
        header_name: header_value,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                model["api_url"],
                json=body,
                headers=headers,
            )
    except httpx.TimeoutException:
        log_request(model.get("name", ""), prompt, "", "Таймаут")
        return "", "Таймаут запроса"
    except httpx.ConnectError as e:
        log_request(model.get("name", ""), prompt, "", str(e))
        return "", f"Ошибка подключения: {e}"
    except Exception as e:
        log_request(model.get("name", ""), prompt, "", str(e))
        return "", str(e)

    if response.status_code == 401:
        log_request(model.get("name", ""), prompt, "", "401")
        return "", "Неверный API-ключ (401)"
    if response.status_code == 429:
        log_request(model.get("name", ""), prompt, "", "429")
        return "", "Превышен лимит запросов (429)"
    if response.status_code >= 500:
        log_request(model.get("name", ""), prompt, "", f"HTTP {response.status_code}")
        return "", f"Ошибка сервера ({response.status_code})"
    if response.status_code != 200:
        log_request(model.get("name", ""), prompt, "", f"HTTP {response.status_code}")
        return "", f"Ошибка HTTP {response.status_code}: {response.text[:200]}"

    try:
        data = response.json()
    except Exception:
        return "", "Некорректный ответ (не JSON)"

    # Извлечение текста из OpenAI-совместимого формата
    choices = data.get("choices", [])
    if not choices:
        return "", "Пустой ответ от API"

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        log_request(model.get("name", ""), prompt, "", "Пустой ответ")
        return "", "Пустое содержимое ответа"

    log_request(model.get("name", ""), prompt, content.strip())
    return content.strip(), None


def send_prompt_to_models(
    models: list[dict],
    prompt: str,
    timeout: float = 60.0,
    delay_between_requests: float = 2.0
) -> list[dict]:
    """
    Отправляет промт в несколько моделей последовательно с задержкой.
    delay_between_requests — пауза в секундах между запросами (снижает риск 429).
    Возвращает список: [{"model": dict, "response": str, "error": str|None}, ...]
    """
    results = []
    for i, model in enumerate(models):
        if i > 0:
            log.info("Пауза %.1f с перед запросом к %s", delay_between_requests, model.get("name", "?"))
            time.sleep(delay_between_requests)
        response_text, error = send_prompt_to_model(model, prompt, timeout)
        results.append({
            "model": model,
            "response": response_text,
            "error": error,
        })
    return results
