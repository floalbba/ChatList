"""Логирование запросов к API."""

from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "requests.log"


def log_request(model_name: str, prompt: str, response: str, error: str = None):
    """Записывает запрос в лог."""
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().isoformat()
    status = "OK" if error is None else f"ERROR: {error}"
    entry = f"[{timestamp}] {model_name} | {status}\n"
    if prompt:
        entry += f"  Prompt: {prompt[:200]}{'...' if len(prompt) > 200 else ''}\n"
    if response and not error:
        entry += f"  Response: {response[:200]}{'...' if len(response) > 200 else ''}\n"
    entry += "\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
