"""Connectors for local Ollama and OpenAI-compatible chat servers."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelError(RuntimeError):
    pass


def chat_completion(settings: dict, messages: list[dict[str, str]]) -> str:
    provider = settings.get("model_provider", "disabled")
    model = str(settings.get("model_name", "")).strip()
    base = str(settings.get("model_base_url", "")).rstrip("/")
    if provider == "disabled":
        raise ModelError("Провайдер модели не настроен")
    if not model or not base:
        raise ModelError("Укажите адрес сервера и название модели")
    if provider == "ollama":
        url = base + "/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
    elif provider == "openai_compatible":
        url = base + "/chat/completions"
        payload = {"model": model, "messages": messages, "stream": False}
    else:
        raise ModelError("Неизвестный провайдер модели")
    headers = {"Content-Type": "application/json"}
    key = str(settings.get("model_api_key", "")).strip()
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(url, json.dumps(payload).encode(), headers, method="POST")
    try:
        with urlopen(request, timeout=120) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise ModelError(f"Сервер модели недоступен: {exc}") from exc
    try:
        result = data["message"]["content"] if provider == "ollama" else data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError("Сервер вернул ответ неизвестного формата") from exc
    if not isinstance(result, str) or not result.strip():
        raise ModelError("Модель вернула пустой ответ")
    return result.strip()
