"""The AIProvider interface: the ONLY place FALCON talks to an AI model.

    FALCON code ──► AIProvider ──► OllamaProvider ──HTTP/JSON──► Ollama on 127.0.0.1:11434
                               └─► FakeProvider (tests: predictable, no model needed)

Swapping in a different model or runtime later means writing one new class, not touching the
features. No SDK: Ollama's API is plain HTTP + JSON, so the standard library is enough.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import get_settings


class AIUnavailable(Exception):
    """The AI service is not running, or the model is missing. Features degrade, never crash."""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    duration_ms: int = 0
    output_tokens: int = 0


@dataclass
class AIStatus:
    available: bool
    chat_model: str
    embed_model: str
    chat_model_ready: bool
    embed_model_ready: bool
    message: str


class AIProvider(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        schema: dict[str, Any] | None = None,
    ) -> ChatReply: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def status(self) -> AIStatus: ...


class OllamaProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.url = settings.ollama_url.rstrip("/")
        # urlopen also reads file:// and other schemes; only plain web addresses are allowed,
        # so a mistaken setting can never make FALCON read local files.
        if urllib.parse.urlsplit(self.url).scheme not in ("http", "https"):
            raise ValueError("OLLAMA_URL must start with http:// or https://")
        self.chat_model = settings.ai_chat_model
        self.embed_model = settings.ai_embed_model
        self.timeout = settings.ai_timeout_seconds

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # B310 (urlopen accepts file://): safe, the scheme is checked in __init__.
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            raise AIUnavailable(f"The AI service refused the request: {detail}") from error
        except TimeoutError as error:
            raise AIUnavailable(
                f"The local AI model took longer than {self.timeout} s to answer. "
                "Try a shorter question, or a smaller model (AI_CHAT_MODEL=qwen3:4b)."
            ) from error
        except (urllib.error.URLError, ConnectionError) as error:
            if isinstance(getattr(error, "reason", None), TimeoutError):
                raise AIUnavailable(
                    f"The local AI model took longer than {self.timeout} s to answer."
                ) from error
            raise AIUnavailable(
                "The local AI service (Ollama) is not reachable. Start Ollama and try again."
            ) from error

    def chat(self, messages, tools=None, schema=None) -> ChatReply:
        body: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "stream": False,
            # Qwen3 can "think aloud" first; that doubles the wait on a CPU. Off: tools and
            # schemas give the structure we need.
            "think": False,
            # num_predict caps the reply length: a model that starts rambling or repeating
            # itself is stopped instead of running until the timeout.
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 700},
            "keep_alive": "15m",  # keep the model in memory between questions
        }
        if tools:
            body["tools"] = tools
        if schema:
            body["format"] = schema  # constrained output: the reply MUST match this JSON schema
        started = time.monotonic()
        data = self._post("/api/chat", body)
        message = data.get("message") or {}
        calls = [
            ToolCall(c["function"]["name"], _as_dict(c["function"].get("arguments")))
            for c in message.get("tool_calls") or []
        ]
        return ChatReply(
            content=message.get("content") or "",
            tool_calls=calls,
            duration_ms=int((time.monotonic() - started) * 1000),
            output_tokens=int(data.get("eval_count") or 0),
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post(
            "/api/embed", {"model": self.embed_model, "input": texts, "keep_alive": "15m"}
        )
        return data["embeddings"]

    def status(self) -> AIStatus:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as response:  # nosec B310
                names = {m["name"] for m in json.loads(response.read()).get("models", [])}
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            return AIStatus(
                False,
                self.chat_model,
                self.embed_model,
                False,
                False,
                "Ollama is not running. Start it to use AI features.",
            )
        chat_ready = _has(names, self.chat_model)
        embed_ready = _has(names, self.embed_model)
        pairs = ((self.chat_model, chat_ready), (self.embed_model, embed_ready))
        missing = [model for model, ready in pairs if not ready]
        return AIStatus(
            available=not missing,
            chat_model=self.chat_model,
            embed_model=self.embed_model,
            chat_model_ready=chat_ready,
            embed_model_ready=embed_ready,
            message="Ready."
            if not missing
            else f"Download missing model(s): ollama pull {' '.join(missing)}",
        )


def _has(names: set[str], model: str) -> bool:
    return model in names or f"{model}:latest" in names


def _as_dict(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    try:
        return json.loads(arguments or "{}")
    except (TypeError, ValueError):
        return {}


class DisabledProvider:
    """Used when AI is switched off in settings."""

    def _off(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AIUnavailable("AI features are switched off on this server.")

    chat = _off
    embed = _off

    def status(self) -> AIStatus:
        settings = get_settings()
        return AIStatus(
            False,
            settings.ai_chat_model,
            settings.ai_embed_model,
            False,
            False,
            "AI features are switched off on this server.",
        )


_current: AIProvider | None = None


def current() -> AIProvider:
    """The provider in use (created on first use)."""
    global _current
    if _current is None:
        _current = OllamaProvider() if get_settings().ai_enabled else DisabledProvider()
    return _current


def use(provider: AIProvider | None) -> None:
    """Swap the provider (tests use a FakeProvider; None = back to the default)."""
    global _current
    _current = provider
