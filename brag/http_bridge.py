"""HTTP bridge (port 8765, mapped to localhost only on the host).

Serves:
- /file/<store-relative-path>   knowledge-store documents for the browser, so search
                                results can deep-link to a PDF page (#page=N)
- /setup + /api/...             the browser-based setup wizard — ONLY when
                                SETUP_MODE=1 (the one-shot `setup` compose
                                service); the persistent app keeps it disabled
- /healthz                      liveness probe
"""

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brag import config

SETUP_PAGE = Path(__file__).parent / "setup_page.html"

# Setup API bodies are tiny JSON — cap the read so a loopback client cannot
# exhaust memory with a huge Content-Length.
MAX_BODY_BYTES = 1_000_000

# The setup page uses inline script/style and only talks to its own origin.
# A strict CSP keeps it from loading or exfiltrating to anywhere else — a
# second line of defence behind output-escaping on the page itself.
SETUP_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
)

# Only requests addressed to the loopback interface are served. The bridge
# binds 0.0.0.0 (Docker port-publishing connects via the container's eth0, so
# binding 127.0.0.1 in-container would break the host mapping), so this
# Host-header allowlist is what actually enforces "localhost only" and defeats
# DNS-rebinding attacks against the setup API.
LOOPBACK_NAMES = ("localhost", "127.0.0.1", "::1")


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep container logs quiet
        pass

    # ── GET ─────────────────────────────────────────────────────
    def do_GET(self):  # noqa: N802 — http.server API
        if not self._host_ok():
            self._send(403, b"forbidden", "text/plain")
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            self._send(200, b"ok", "text/plain")
        elif parsed.path in ("/", "/setup"):
            # The wizard is served only by the one-shot setup service (the only
            # one with the project + Claude-config mounts). On the persistent
            # app, point the user at the launcher instead of a wizard that
            # could not write anything anyway.
            if not config.SETUP_MODE:
                self._send(200,
                           b"Setup is not running here. Double-click setup.command "
                           b"(macOS) or setup.bat (Windows) to (re-)configure BRAG.",
                           "text/plain")
                return
            self._send(200, SETUP_PAGE.read_bytes(), "text/html; charset=utf-8",
                       extra={"Content-Security-Policy": SETUP_CSP})
        elif parsed.path.startswith("/file/"):
            rel = urllib.parse.unquote(parsed.path[len("/file/"):])
            params = urllib.parse.parse_qs(parsed.query)
            project = (params.get("project", [""])[0] or "").strip()
            self._serve_vault_file(rel, project)
        else:
            self._send(404, b"not found", "text/plain")

    # ── POST (setup API) ────────────────────────────────────────
    def do_POST(self):  # noqa: N802
        if not self._host_ok() or not self._origin_ok():
            self._send_json(403, {"ok": False, "message": "forbidden"})
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY_BYTES:
                self._send_json(413, {"ok": False, "message": "request too large"})
                return
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "message": "invalid request"})
            return

        # Shared model service — available on the PERSISTENT app (SETUP_MODE off):
        # the per-project MCP clients are thin (load no models) and call this, so
        # the heavy embed/retrieve/rerank runs exactly once, in this process.
        if parsed.path == "/api/search":
            self._api_search(body)
            return
        if parsed.path == "/api/index-op":
            self._api_index_op(body)
            return

        # The config-writing setup API exists only in the one-shot setup service.
        if not config.SETUP_MODE:
            self._send_json(404, {"ok": False, "message": "setup not active"})
            return

        if parsed.path == "/api/validate-key":
            from brag.setup_core import list_models
            ok, message, models = list_models(
                str(body.get("provider", "gemini")), str(body.get("key", "")))
            self._send_json(200, {"ok": ok, "message": message, "models": models})
        elif parsed.path == "/api/list-folders":
            self._list_folders()
        elif parsed.path == "/api/check-local":
            self._check_local(body)
        elif parsed.path == "/api/setup":
            self._apply_setup(body)
        elif parsed.path == "/api/current-settings":
            self._current_settings()
        else:
            self._send_json(404, {"ok": False, "message": "unknown endpoint"})

    def _current_settings(self):
        """Current .env-derived settings for the wizard's 'change a setting' view,
        so a user can tweak one thing (e.g. the reranker) without re-walking the
        whole wizard. Never returns the API key itself — only whether one is set."""
        from brag import setup_core
        env = setup_core.read_existing_env()
        profile = env.get("PROFILE", "")
        key_env = setup_core.PROFILES.get(profile, {}).get("key_env")
        self._send_json(200, {
            "configured": bool(profile),
            "profile": profile,
            "language": env.get("VAULT_LANGUAGE", ""),
            "rerank_profile": env.get("RERANK_PROFILE", "eco"),
            "vision_enabled": env.get("VISION_ENABLED", "true").lower() != "false",
            "llm_model": env.get("LLM_MODEL", ""),
            "has_key": bool(key_env and env.get(key_env)),
        })

    def _list_folders(self):
        """Top-level folders of the chosen project, for the wizard's optional
        'exclude from index' picker. Best-effort: returns [] if the project is
        not mounted/listable yet — the "_"-prefix convention works without it.
        WissensWIKI, hidden and already-"_" dirs are never offered (they can't
        be corpus anyway)."""
        folders = []
        try:
            for p in sorted(config.VAULT.iterdir()):
                name = p.name
                if not p.is_dir() or name == config.WISSENSWIKI_NAME \
                        or name.startswith((".", "_")):
                    continue
                folders.append({"name": name, "excluded": name in config.EXCLUDE_DIRS})
        except OSError:
            folders = []
        self._send_json(200, {"folders": folders})

    def _check_local(self, body: dict):
        """Probe LM Studio on the host and list its loaded models."""
        import urllib.request
        url, app = "http://host.docker.internal:1234/v1/models", "LM Studio"
        hint = ("Open LM Studio, go to the Developer tab and click "
                "'Start Server', then check again.")
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except (OSError, json.JSONDecodeError):
            self._send_json(200, {"ok": False, "models": [],
                                  "message": f"{app} is not reachable. {hint}"})
            return

        # Embeddings are ALWAYS local (arctic, in-container) in every profile —
        # the local profile only needs a chat model, so we gate on that alone.
        chat_models = [m for m in models if "embed" not in m.lower()]
        if not chat_models:
            self._send_json(200, {
                "ok": False, "models": [],
                "message": (f"{app} is running, but no language model is "
                            "loaded yet — see the steps above."),
            })
            return
        self._send_json(200, {
            "ok": True, "models": chat_models,
            "message": f"{app} is running with {len(chat_models)} model(s).",
        })

    def _apply_setup(self, body: dict):
        from brag import setup_core
        steps = []
        try:
            setup_core.write_env(
                profile=str(body.get("profile", "cloud")),
                api_key=str(body.get("api_key", "")),
                language=str(body.get("language", "english")),
                vault_path=str(body.get("vault_path", "")).strip(),
                llm_model=str(body.get("llm_model", "")).strip(),
                rerank_profile=str(body.get("rerank_profile", "eco")).strip() or "eco",
                vision_enabled=bool(body.get("vision_enabled", True)),
                exclude_dirs=str(body.get("exclude_dirs", "")).strip(),
            )
            steps.append({"ok": True, "message": "Configuration saved"})
        except OSError as e:
            steps.append({"ok": False, "message": f"Could not save configuration: {e}"})
            self._send_json(200, {"ok": False, "steps": steps})
            return

        # Only fabricate the default in-project vault when NO vault is chosen yet
        # — neither a wizard field nor an existing VAULT_PATH in .env (which the
        # host launcher's picker/relocation sets, e.g. <RAG folder>\WissensWIKI).
        # Otherwise create_vault() would make the wrong folder and the mount of
        # the real vault would be defeated.
        has_vault = (bool(str(body.get("vault_path", "")).strip())
                     or bool(setup_core.read_existing_env().get("VAULT_PATH")))
        if has_vault:
            steps.append({"ok": True, "message": "Using your chosen knowledge folder"})
        else:
            created = setup_core.create_vault()
            steps.append({"ok": True, "message":
                          "Knowledge folder created" if created
                          else "Knowledge folder already exists — kept untouched"})

        claude_ok, claude_msg = setup_core.write_claude_config()
        steps.append({"ok": claude_ok, "message": claude_msg})

        setup_core.mark_setup_complete()
        steps.append({"ok": True, "message": "Restarting with your settings…"})
        response = {
            "ok": True, "steps": steps,
            "claude_manual_snippet": not claude_ok,
        }
        if not claude_ok:
            # Hand the exact JSON entry back so the user can paste it directly,
            # instead of being sent to the FAQ.
            response["claude_snippet"] = json.dumps(
                {"mcpServers": {setup_core.MCP_KEY: setup_core.MCP_ENTRY}},
                indent=2,
            )
            response["claude_config_path"] = (
                "claude_desktop_config.json — on macOS at "
                "~/Library/Application Support/Claude/claude_desktop_config.json, "
                "on Windows at %APPDATA%\\Claude\\claude_desktop_config.json"
            )
        self._send_json(200, response)

    def _api_search(self, body: dict):
        """Shared search service: a thin per-project MCP client POSTs here and the
        heavy embed/retrieve/rerank runs in this one persistent process — so the
        models live in RAM exactly once no matter how many connectors are open.
        `project` selects the per-project collection via the registry; omit it for
        the single-project default."""
        from brag import registry
        from brag.search.query import search as run_search

        project = str(body.get("project", "")).strip()
        collection = None
        if project:
            collection = registry.get_collection(project)
            if collection is None:
                self._send_json(404, {"ok": False, "message":
                    f"unknown project '{project}' — re-run setup for this project"})
                return
        raw_top = body.get("top_k")
        top_k = raw_top if isinstance(raw_top, int) and raw_top > 0 else None
        raw_mps = body.get("max_per_source")
        max_per_source = raw_mps if isinstance(raw_mps, int) and raw_mps > 0 else None
        mode = str(body.get("mode", "normal") or "normal")
        meta = body.get("meta")
        try:
            hits = run_search(
                str(body.get("query", "")),
                top_k=top_k,
                mode=mode,
                reranking=body.get("reranking"),
                max_chunks_per_source=max_per_source,
                collection_name=collection,
                doc_type=str(body.get("doc_type", "")) or None,
                chunk_type=str(body.get("chunk_type", "")) or None,
                year_min=body.get("year_min") or None,
                year_max=body.get("year_max") or None,
                source_file=str(body.get("source_file", "")) or None,
                meta=meta if isinstance(meta, dict) else None,
            )
        except Exception as e:  # noqa: BLE001 — a search error must not kill the thread
            self._send_json(500, {"ok": False,
                                  "message": f"search failed: {str(e)[:200]}"})
            return
        self._send_json(200, {"ok": True, "hits": hits})

    def _api_index_op(self, body: dict):
        """Tool dispatcher for the thin MCP client: runs an index/file tool in
        this persistent process (which holds the models + the vault) and returns
        its text. `project` scopes the index reads to that project's collection;
        the file-side ops use the vault paths (per-project scoping arrives with
        config.project_context in a later phase — today there is one vault)."""
        from brag import registry, tools

        project = str(body.get("project", "")).strip()
        rec = None
        if project:
            rec = registry.get(project)
            if rec is None:
                self._send_json(404, {"ok": False, "message":
                    f"unknown project '{project}' — re-run setup for this project"})
                return
        collection = rec.get("collection") if rec else None
        op = str(body.get("op", "")).strip()
        a = body.get("args") if isinstance(body.get("args"), dict) else {}

        def _int(value, default=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        ops = {
            "list_sources": lambda: tools.list_sources(
                doc_type=str(a.get("doc_type", "")), collection_name=collection),
            "inspect_chunks": lambda: tools.inspect_chunks(
                str(a.get("source_file", "")), page=_int(a.get("page")),
                limit=_int(a.get("limit", 10), 10), collection_name=collection),
            "read_source": lambda: tools.read_source(
                str(a.get("source_file", "")), page_from=_int(a.get("page_from")),
                page_to=_int(a.get("page_to")), limit=_int(a.get("limit", 25), 25),
                collection_name=collection),
            "remove_source": lambda: tools.remove_source(str(a.get("source_file", ""))),
            "rename_source": lambda: tools.rename_source(
                str(a.get("source_file", "")), str(a.get("new_name", ""))),
            "save_passage": lambda: tools.save_passage(
                str(a.get("topic", "")), str(a.get("text", "")),
                str(a.get("source", "")), page=str(a.get("page", "")),
                note=str(a.get("note", ""))),
            "list_passages": lambda: tools.list_passages(topic=str(a.get("topic", ""))),
            "list_notebook": tools.list_notebook,
            "read_note": lambda: tools.read_note(str(a.get("path", ""))),
            "write_note": lambda: tools.write_note(
                str(a.get("path", "")), str(a.get("content", ""))),
            "recent_sources": lambda: tools.recent_sources(
                limit=_int(a.get("limit", 15), 15), collection_name=collection),
            "set_metadata": lambda: tools.set_metadata(
                str(a.get("folder", "")), str(a.get("key", "")),
                str(a.get("value", ""))),
            "delete_note": lambda: tools.delete_note(
                str(a.get("path", "")), confirm=bool(a.get("confirm", False))),
            "delete_passage": lambda: tools.delete_passage(
                str(a.get("topic", "")), confirm=bool(a.get("confirm", False))),
            "move_note": lambda: tools.move_note(
                str(a.get("path", "")), str(a.get("new_path", ""))),
        }
        handler = ops.get(op)
        if handler is None:
            self._send_json(404, {"ok": False, "message": f"unknown op '{op}'"})
            return
        try:
            # Scope the vault paths + collection to this project for the call so
            # the file-side ops (remove/rename/save_passage/notebook) and the
            # index mutations target the right project. The ContextVar is
            # per-thread, so concurrent requests never cross over. A None record
            # is the single-project default.
            with config.project_context(rec):
                text = handler()
        except Exception as e:  # noqa: BLE001 — a tool error must not kill the thread
            self._send_json(500, {"ok": False, "message": f"{op} failed: {str(e)[:200]}"})
            return
        self._send_json(200, {"ok": True, "text": text})

    # ── helpers ─────────────────────────────────────────────────
    def _host_ok(self) -> bool:
        """Accept only requests addressed to localhost (anti DNS-rebinding)."""
        host = self.headers.get("Host", "")
        name = host.rsplit(":", 1)[0].strip("[]").lower() if host else ""
        return name in LOOPBACK_NAMES

    def _origin_ok(self) -> bool:
        """For state-changing POSTs, reject cross-origin browser requests."""
        origin = self.headers.get("Origin")
        if not origin:
            return True  # non-browser caller; the Host check still applies
        try:
            name = (urllib.parse.urlparse(origin).hostname or "").lower()
        except ValueError:
            return False
        return name in LOOPBACK_NAMES

    def _serve_vault_file(self, rel: str, project: str = ""):
        # A deep link from a non-default project carries ?project=<slug>; resolve
        # the path against THAT project's vault (not the default one), reusing the
        # same per-request context as the tool dispatcher. Resolution runs INSIDE
        # the context so it validates against the correct vault.
        rec = None
        if project:
            from brag import registry
            rec = registry.get(project)
        with config.project_context(rec):
            base = config.VAULT
            # An explicit traversal / absolute-path escape is forbidden outright,
            # BEFORE any tolerant lookup, so it stays a clear 403 (not a 404).
            try:
                (base / rel).resolve().relative_to(base.resolve())
            except ValueError:
                self._send(403, b"forbidden", "text/plain")
                return
            except OSError:
                pass
            target = resolve_corpus_file(base, rel)
            if target is None:
                import sys
                print(f"[bridge] /file 404 — no corpus file matched {rel!r} "
                      f"under {base}", file=sys.stderr)
                self._send(404, ("file not found — this document is not where the "
                                 "index expects it under your project folder "
                                 f"(looked for: {rel}). If you moved or renamed it, "
                                 "ask BRAG to re-index, then try the link again."
                                 ).encode("utf-8"), "text/plain; charset=utf-8")
                return
            # Cross-Origin-Resource-Policy stops a cross-origin web page from
            # embedding/reading these bytes; with the Host allowlist and no CORS
            # headers, the served file stays loopback-same-origin only (SEC-01).
            if target.suffix.lower() == ".pdf":
                # PDFs render inline so the browser can jump to #page=N.
                self._send(200, target.read_bytes(), "application/pdf",
                           extra={"Cross-Origin-Resource-Policy": "same-origin"})
            else:
                # Never serve knowledge-store content (.html/.md/…) as active,
                # same-origin HTML — hand it back as a download (stored-XSS hardening).
                self._send(200, target.read_bytes(), "application/octet-stream",
                           extra={"Content-Disposition": "attachment",
                                  "Cross-Origin-Resource-Policy": "same-origin"})

    def _send(self, code: int, body: bytes, mime: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode(), "application/json")


def resolve_corpus_file(base, rel: str):
    """Map a /file/<rel> request to a real file under `base`, robustly. Returns a
    Path inside `base`, or None — and NEVER escapes `base` (the traversal guard
    rejects '..' and symlinks pointing outside).

    Why this is tolerant rather than a single `base / rel` lookup: a stored
    rel_path can mismatch the on-disk name in two real-world ways —
      1. Unicode normalization (macOS writes file names as NFD; an index built
         elsewhere, or an older BRAG, may hold NFC) — so a literal join misses;
      2. a rel_path that lost its subfolder (older ingest stored just the
         basename) — so `base/name.pdf` 404s while the file sits in `Sub/`.
    We therefore try the literal + NFC + NFD forms first, then fall back to a
    corpus scan that matches the normalized relative path, else the bare file
    name. The scan is scoped to is_corpus_path so nothing outside the corpus is
    served, and only runs when the fast path misses (rare once rel_path is sound).
    """
    import unicodedata
    from pathlib import Path

    base = Path(base)
    base_resolved = base.resolve()

    def _guarded(cand: Path):
        try:
            t = cand.resolve()
            t.relative_to(base_resolved)   # blocks ../ and symlink-escape
        except (ValueError, OSError):
            return None
        return t if t.is_file() else None

    # 1. Fast path: literal + Unicode-normalized variants of the whole rel path.
    seen = set()
    for form in (rel, unicodedata.normalize("NFC", rel), unicodedata.normalize("NFD", rel)):
        if form in seen:
            continue
        seen.add(form)
        hit = _guarded(base / form)
        if hit is not None:
            return hit

    # 2. Fallback scan: normalization-insensitive match on the relative path,
    #    else on the bare file name (covers a rel_path that lost its folder).
    want_rel = unicodedata.normalize("NFC", rel).lower()
    want_name = unicodedata.normalize("NFC", rel.rsplit("/", 1)[-1]).lower()
    by_name = None
    try:
        for p in base.rglob("*"):
            try:
                if not p.is_file() or not config.is_corpus_path(p):
                    continue
            except OSError:
                continue
            rp = unicodedata.normalize("NFC", p.relative_to(base).as_posix()).lower()
            if rp == want_rel:
                hit = _guarded(p)
                if hit is not None:
                    return hit
            if by_name is None and \
                    unicodedata.normalize("NFC", p.name).lower() == want_name:
                by_name = _guarded(p)
    except OSError:
        pass
    return by_name


def pdf_link(rel_path: str, page: int | None = None, project: str = "") -> str:
    """Public link that opens the document in the host browser at a page. For a
    non-default project it carries ?project=<slug> so the file server resolves
    the path against that project's vault, not the default one."""
    quoted = urllib.parse.quote(rel_path)
    query = f"?project={urllib.parse.quote(project)}" if project else ""
    anchor = f"#page={page}" if page else ""
    return f"{config.BRIDGE_PUBLIC_URL}/file/{quoted}{query}{anchor}"


def start_bridge_in_background() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", config.BRIDGE_PORT), BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"HTTP bridge listening on port {config.BRIDGE_PORT}")
    return server
