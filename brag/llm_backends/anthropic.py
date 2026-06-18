"""Anthropic / Claude LLM backend (Profile: anthropic).

Uses the Anthropic Messages API over raw HTTP (urllib) to avoid adding the
Anthropic SDK as a Docker dependency — consistent with the other HTTP-based
backends here. Claude has no embedding API, so the "anthropic" profile pairs
this LLM with local embeddings (see profiles.py).

Default model claude-haiku-4-5 is the cheapest Claude model and is multimodal,
so it also handles figure descriptions in the vision pass.
"""

import json
import urllib.request

from brag import config
from brag.llm_backends.base import LLMBackend
from brag.llm_backends.retry import call_with_retry

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicLLM(LLMBackend):
    vision_capable = True  # the default claude-haiku-4-5 is multimodal

    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file "
                "(get a key at https://console.anthropic.com/)."
            )

    def chat(
        self, prompt: str, max_tokens: int = 1024, images: list[str] | None = None
    ) -> str | None:
        if images:
            content: list = [{"type": "text", "text": prompt}]
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img,
                    },
                })
        else:
            content = prompt

        def call():
            payload = json.dumps({
                "model": config.LLM_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": content}],
            }).encode()
            req = urllib.request.Request(
                API_URL, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": API_VERSION,
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            if not text:
                raise ValueError("empty response")
            return text

        return call_with_retry(call, label="anthropic chat")
