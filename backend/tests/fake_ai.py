"""Stand-ins for the local AI, so tests are fast, offline and give the same result every run."""

import hashlib
import json
import math
import re
from collections.abc import Iterable
from typing import Any

from app.ai.provider import AIStatus, AIUnavailable, ChatReply, ToolCall

DIMENSIONS = 384


def word_vector(text: str) -> list[float]:
    """A crude "embedding": each word adds 1 to one of 384 slots. Shared words → similar
    vectors. Good enough to test the plumbing; real meaning comes from the real model."""
    vector = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS
        vector[slot] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class OfflineProvider:
    """Behaves like Ollama when it is not running."""

    def chat(self, *_: Any, **__: Any) -> ChatReply:
        raise AIUnavailable("The local AI service (Ollama) is not reachable.")

    embed = chat

    def status(self) -> AIStatus:
        return AIStatus(False, "fake-chat", "fake-embed", False, False, "Ollama is not running.")


class FakeProvider:
    """Embeds with word_vector; answers chat with scripted replies, in order."""

    def __init__(self, replies: Iterable[ChatReply | dict[str, Any] | str] = ()) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None, schema=None) -> ChatReply:
        self.calls.append({"messages": messages, "tools": tools, "schema": schema})
        reply = self.replies.pop(0) if self.replies else "No more scripted replies."
        if isinstance(reply, dict):
            return ChatReply(content=json.dumps(reply))
        if isinstance(reply, str):
            return ChatReply(content=reply)
        return reply

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [word_vector(t) for t in texts]

    def status(self) -> AIStatus:
        return AIStatus(True, "fake-chat", "fake-embed", True, True, "Ready.")


def tool_call(name: str, **arguments: Any) -> ChatReply:
    return ChatReply(content="", tool_calls=[ToolCall(name, arguments)])
