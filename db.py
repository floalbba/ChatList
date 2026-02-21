"""Модуль работы с SQLite. Инкапсулирует весь доступ к базе данных."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Путь к файлу БД
DB_PATH = Path(__file__).parent / "chatlist.db"


def get_connection() -> sqlite3.Connection:
    """Возвращает подключение к БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Инициализация БД: создание таблиц при первом запуске."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                prompt TEXT NOT NULL,
                tags TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_prompts_created_at ON prompts(created_at);
            CREATE INDEX IF NOT EXISTS idx_prompts_tags ON prompts(tags);

            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_url TEXT NOT NULL,
                api_id TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                model_type TEXT DEFAULT 'openai'
            );
            CREATE INDEX IF NOT EXISTS idx_models_is_active ON models(is_active);

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER NOT NULL,
                model_id INTEGER,
                model_name TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
                FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_results_prompt_id ON results(prompt_id);
            CREATE INDEX IF NOT EXISTS idx_results_model_id ON results(model_id);
            CREATE INDEX IF NOT EXISTS idx_results_created_at ON results(created_at);

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()

        # Добавить модель OpenRouter по умолчанию, если таблица пуста
        cur = conn.execute("SELECT COUNT(*) FROM models")
        if cur.fetchone()[0] == 0:
            conn.execute(
                """INSERT INTO models (name, api_url, api_id, is_active, model_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    "openai/gpt-4o-mini",
                    "https://openrouter.ai/api/v1/chat/completions",
                    "OPENROUTER_API_KEY",
                    1,
                    "openrouter",
                )
            )
            conn.commit()
    finally:
        conn.close()


# --- prompts ---

def create_prompt(prompt: str, tags: str = "") -> int:
    """Создаёт промт. Возвращает id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO prompts (prompt, tags) VALUES (?, ?)",
            (prompt, tags)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_prompts(
    search: Optional[str] = None,
    order_by: str = "created_at",
    order_desc: bool = True
) -> list[dict]:
    """Возвращает список промтов. Опционально: поиск и сортировка."""
    conn = get_connection()
    try:
        order_col = "created_at" if order_by == "created_at" else "prompt"
        direction = "DESC" if order_desc else "ASC"
        if search:
            cur = conn.execute(
                f"SELECT * FROM prompts WHERE prompt LIKE ? OR tags LIKE ? ORDER BY {order_col} {direction}",
                (f"%{search}%", f"%{search}%")
            )
        else:
            cur = conn.execute(
                f"SELECT * FROM prompts ORDER BY {order_col} {direction}"
            )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_prompt_by_id(prompt_id: int) -> Optional[dict]:
    """Возвращает промт по id."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_prompt(prompt_id: int, prompt: str, tags: str = "") -> int:
    """Обновляет промт. Возвращает количество изменённых строк."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE prompts SET prompt = ?, tags = ? WHERE id = ?",
            (prompt, tags, prompt_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_prompt(prompt_id: int) -> int:
    """Удаляет промт. Возвращает количество удалённых строк."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- models ---

def create_model(name: str, api_url: str, api_id: str, is_active: int = 1, model_type: str = "openai") -> int:
    """Создаёт модель. Возвращает id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO models (name, api_url, api_id, is_active, model_type) VALUES (?, ?, ?, ?, ?)",
            (name, api_url, api_id, is_active, model_type)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_models() -> list[dict]:
    """Возвращает все модели."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM models ORDER BY name")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_active_models() -> list[dict]:
    """Возвращает только активные модели (is_active=1)."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM models WHERE is_active = 1 ORDER BY name")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_model_by_id(model_id: int) -> Optional[dict]:
    """Возвращает модель по id."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM models WHERE id = ?", (model_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_model(model_id: int, name: str, api_url: str, api_id: str, is_active: int, model_type: str = "openai") -> int:
    """Обновляет модель. Возвращает количество изменённых строк."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE models SET name = ?, api_url = ?, api_id = ?, is_active = ?, model_type = ? WHERE id = ?",
            (name, api_url, api_id, is_active, model_type, model_id)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_model(model_id: int) -> int:
    """Удаляет модель. Возвращает количество удалённых строк."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- results ---

def create_result(prompt_id: int, model_id: Optional[int], model_name: str, response: str) -> int:
    """Сохраняет результат. Возвращает id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO results (prompt_id, model_id, model_name, response) VALUES (?, ?, ?, ?)",
            (prompt_id, model_id, model_name, response)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_results(prompt_id: Optional[int] = None) -> list[dict]:
    """Возвращает сохранённые результаты. Опционально: фильтр по prompt_id."""
    conn = get_connection()
    try:
        if prompt_id is not None:
            cur = conn.execute(
                "SELECT * FROM results WHERE prompt_id = ? ORDER BY created_at DESC",
                (prompt_id,)
            )
        else:
            cur = conn.execute("SELECT * FROM results ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_result(result_id: int) -> int:
    """Удаляет результат. Возвращает количество удалённых строк."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


# --- settings ---

def get_setting(key: str) -> Optional[str]:
    """Возвращает значение настройки по ключу."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Записывает настройку (ключ-значение)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()


# Инициализация при импорте
init_db()
