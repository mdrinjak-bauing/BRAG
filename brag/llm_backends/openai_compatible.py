"""OpenAI-compatible LLM backend (the local "hybrid" profile).

Serves LM Studio (localhost:1234/v1), which exposes the OpenAI chat
completions API.
Uses urllib only, no extra dependency. Local models run requests
SEQUENTIALLY by design (parallel local inference can freeze machines).
"""

import json
import re
import time
import urllib.error
import urllib.request

from brag import config
from brag.llm_backends.base import LLMBackend

THINK_TAG = re.compile(r"<think>.*?</think>", re.DOTALL)
TIMEOUT_SECONDS = 900  # generous: local models on weak hardware are slow


class OpenAICompatibleLLM(LLMBackend):
    # Whether the loaded local model is multimodal is unknown up front; we
    # attempt vision and the caller falls back to caption-only context if the
    # model rejects the image (text-only models like llama3.1).
    vision_capable = True

    def __init__(self):
        if not config.LLM_BASE_URL:
            raise EnvironmentError("LLM_BASE_URL is not set for the local profile.")
        self._url = config.LLM_BASE_URL.rstrip("/")

    # A 1x1 transparent PNG — the smallest thing that is unambiguously an image.
    _PROBE_PIXEL = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGNgAQ"
        "AABQABDQottAAAAABJRU5ErkJggg=="
    )

    def can_see_images(self) -> tuple[bool | None, str]:
        """Ask the loaded model one tiny image question. (capable, reason).

        True  — it answered, so it accepts images.
        False — it refused the request; expect caption-only context for figures.
        None  — it could not be asked (server busy or down). NOT the same as
                text-only: telling someone their multimodal model is text-only
                because LM Studio was loading would send them off to change a
                setting that was never the problem.

        Whether a local model is multimodal cannot be read off its name, and the
        ingest only finds out after two failed figures — by which point the run
        is hours old. One request settles it up front.
        """
        import urllib.error

        try:
            antwort = self.chat("What is in this image? Answer in one word.",
                                max_tokens=8, images=[self._PROBE_PIXEL])
        except urllib.error.HTTPError as e:
            return False, (f"the model rejected the image ({e.code}) — figures "
                           "will be indexed by their caption only")
        except OSError as e:
            return None, f"could not reach the model server ({e})"
        if antwort:
            return True, "the model accepted an image"
        return False, ("the model returned nothing for an image — figures will "
                       "be indexed by their caption only")

    def server_alive(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self._url}/models", timeout=5):
                return True
        except OSError:
            return False

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
        # Optional pacing: give the GPU a breather between local calls so it is
        # not pegged continuously (gentler on thermals/power on consumer rigs).
        if config.LOCAL_LLM_PACING_SECONDS > 0:
            time.sleep(config.LOCAL_LLM_PACING_SECONDS)
        payload = {
            "model": config.LLM_MODEL,
            "messages": [{"role": "user", "content": content}],
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
            except urllib.error.HTTPError as e:
                # An HTTP status came back, so the server IS reachable. A 4xx is a
                # CLIENT error — the request itself is bad (e.g. 400 when the
                # prompt exceeds the model's loaded context window). Retrying the
                # IDENTICAL request just 400s again, burning the sleep budget for
                # nothing, so fail fast. The two retryable exceptions are 408
                # (request timeout) and 429 (too many requests); everything else
                # in 4xx is non-retryable. 5xx falls through to the retry path.
                if 400 <= e.code < 500 and e.code not in (408, 429):
                    print(f"  local LLM client error (HTTP {e.code}, not retrying): "
                          f"{str(e)[:100]}")
                    return None
                print(f"  local LLM error (retry {attempt + 1}/3): HTTP {e.code} "
                      f"{str(e)[:80]}")
                time.sleep(2 * (attempt + 1))
            except (OSError, KeyError, json.JSONDecodeError) as e:
                if attempt == 0 and not self.server_alive():
                    print(
                        "  local LLM server is not reachable at "
                        f"{self._url} — is LM Studio running on the host?"
                    )
                    return None
                print(f"  local LLM error (retry {attempt + 1}/3): {str(e)[:100]}")
                time.sleep(2 * (attempt + 1))
        return None
