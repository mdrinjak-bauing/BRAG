"""OpenAI-compatible LLM backend (Profiles B and C).

One client serves both LM Studio (localhost:1234/v1) and Ollama
(localhost:11434/v1) — both expose the OpenAI chat completions API.
Uses urllib only, no extra dependency. Local models run requests
SEQUENTIALLY by design (parallel local inference can freeze machines).
"""

import json
import re
import time
import urllib.error
import urllib.request

from studiolo import config
from studiolo.llm_backends.base import LLMBackend

THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL)
TIMEOUT_SECONDS = 900  # generous: local models on weak hardware are slow


class OpenAICompatibleLLM(LLMBackend):
    def __init__(self):
        if not config.LLM_BASE_URL:
            raise EnvironmentError("LLM_BASE_URL is not set for the local profile.")
        self._url = config.LLM_BASE_URL.rstrip("/")

    def server_alive(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self._url}/models", timeout=5):
                return True
        except OSError:
            return False

    def chat(self, prompt: str, max_tokens: int = 1024) -> str | None:
        payload = {
            "model": config.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    f"{self._url}/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                    data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"] or ""
                text = THINK_TAG.sub("", text).strip()
                if text:
                    return text
            except (OSError, KeyError, json.JSONDecodeError) as e:
                if attempt == 0 and not self.server_alive():
                    print(
                        "  local LLM server is not reachable at "
                        f"{self._url} — is LM Studio / Ollama running on the host?"
                    )
                    return None
                print(f"  local LLM error (retry {attempt + 1}/3): {str(e)[:100]}")
                time.sleep(2 * (attempt + 1))
        return None
