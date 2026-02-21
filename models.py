"""Логика работы с моделями нейросетей."""

import os
from typing import Optional

from dotenv import load_dotenv

import db

# Загрузка переменных из .env
load_dotenv()


def get_active_models() -> list[dict]:
    """Возвращает список активных моделей из БД."""
    return db.get_active_models()


def get_all_models() -> list[dict]:
    """Возвращает все модели из БД."""
    return db.get_models()


def get_api_key(api_id: str) -> Optional[str]:
    """Возвращает API-ключ по имени переменной из .env."""
    return os.getenv(api_id)


def build_request_body(model_type: str, prompt: str, model_name: str = "") -> dict:
    """
    Формирует тело запроса для разных типов API.
    model_type: openai, deepseek, groq
    """
    model_type = (model_type or "openai").lower()

    # Базовый формат OpenAI-совместимый (используют OpenAI, DeepSeek, Groq и др.)
    body = {
        "model": model_name or "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
    }

    if model_type == "groq":
        # Groq использует тот же формат, но model может отличаться (llama, mixtral)
        body["model"] = model_name or "llama-3.1-8b-instant"
    elif model_type == "deepseek":
        body["model"] = model_name or "deepseek-chat"

    return body


def get_auth_header(api_id: str) -> tuple[str, str]:
    """
    Возвращает кортеж (header_name, api_key) для авторизации.
    OpenAI/DeepSeek/Groq используют Bearer в заголовке Authorization.
    """
    key = get_api_key(api_id)
    if not key:
        return ("Authorization", "")
    return ("Authorization", f"Bearer {key}")
