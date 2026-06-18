"""OpenAI / ChatGPT LLM backend (Profile: openai). Raw HTTP, no extra dependency."""

import json
import urllib.request

from brag import config
from brag.llm_backends.base import LLMBackend
from brag.llm_backends.retry import call_with_retry

DEFAULT_URL = "https://api.openai.com/v1"


class OpenAILLM(LLMBackend):
    vision_capable = True  # the default gpt-4o-mini is multimodal

    def __init__(self):
        if not config.OPENAI_API_KEY:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file "
                "(get a key at https://platform.openai.com/api-keys)."
            )

    def chat(
        self, prompt: str, max_tokens: int = 1024, images: list[str] | None = None
    ) -> str | None:
        if images:
            content: list = [{"type": "text", "text": prompt}]
            for img in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img}"},
                })
        else:
            content = prompt

        def call():
            payload = json.dumps({
                "model": config.LLM_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            }).encode()
            req = urllib.request.Request(
                f"{DEFAULT_URL}/chat/completions", data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"] or ""
            if not text:
                raise ValueError("empty response")
            return text

        return call_with_retry(call, label="openai chat")
