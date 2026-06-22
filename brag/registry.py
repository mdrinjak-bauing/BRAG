"""Multi-project registry — the single source of truth for BRAG's projects.

A project is a knowledge folder the user picks at an ARBITRARY location; each one
has its own Qdrant collection and its own MCP connector, while the program, the
~3 GB models and Qdrant are shared. This module owns the registry JSON listing
each project's slug, display name, host folder, mounted vault path and
collection. It is read by the HTTP bridge, the watcher, the compose generator
and setup.

Single-project installs keep working unchanged: when the registry is absent,
callers fall back to the env-derived defaults in `brag.config`. The canonical
file lives on a small shared volume (default /registry/projects.json); override
with the BRAG_REGISTRY env var (used by tests).
"""

import contextlib
import json
import os
import re
from pathlib import Path

SCHEMA_VERSION = 1

# Host-path characters that break Docker Compose interpolation ($) or batch /
# shell quoting, plus the double-quote and newlines that would break the
# double-quoted YAML scalar the compose mount line is emitted as (MP-F06).
# Rejected up front (superset of tools/pick_folder.ps1's set) so a bad path never
# reaches a generated compose mount line. NOTE: the single quote is allowed —
# it is legal and common in folder names ("John's Thesis") and is safe inside a
# double-quoted YAML scalar.
INVALID_PATH_CHARS = set('$&%^!"\n\r')


def registry_path() -> Path:
    """Resolved per call so tests can point BRAG_REGISTRY at a temp file."""
    return Path(os.environ.get("BRAG_REGISTRY", "/registry/projects.json"))


# Lowercase German umlauts transliterated so a name like "Über-Projekt" yields a
# clean ASCII slug ("ueber-projekt") that is safe as a Qdrant collection name, a
# /projects/<slug> mount path and an MCP key. The DISPLAY name keeps the umlauts.
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def slugify(name: str) -> str:
    """ASCII, folder/collection/MCP-key-safe slug: lowercase, umlauts
    transliterated, runs of any other non-[a-z0-9-] char collapsed to '_'."""
    slug = str(name).strip().lower().translate(_UMLAUTS)
    # strip leading/trailing '_' AND '-' so an all-dash name falls back to a
    # default rather than yielding a slug like "---".
    slug = re.sub(r"[^a-z0-9-]+", "_", slug).strip("_-")
    return slug or "project"


def collection_for(base_collection: str, slug: str) -> str:
    """Per-project collection name = base + '__' + slug. Keeps the base's
    'asb_<backend>_<dim>' prefix so storage.orphaned_collections still recognizes
    it and so all projects stay on the same embedding dimension."""
    return f"{base_collection}__{slug}"


def normalize_host_path(path: str) -> str:
    """Backslashes -> forward slashes, trailing slash trimmed — the form a
    compose bind-mount line wants for a Windows host path."""
    return str(path).strip().replace("\\", "/").rstrip("/")


def validate_host_path(path: str) -> tuple[bool, str]:
    if not path or not str(path).strip():
        return False, "empty path"
    bad = sorted(INVALID_PATH_CHARS & set(str(path)))
    if bad:
        return False, "path contains unsupported character(s): " + " ".join(bad)
    return True, ""


def load() -> dict:
    """Return the registry dict, or an empty one on any error (never raises) —
    so a missing/corrupt registry degrades to 'no extra projects', not a crash."""
    try:
        p = registry_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("projects"), list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"version": SCHEMA_VERSION, "projects": []}


def projects() -> list[dict]:
    return load().get("projects", [])


def get(slug: str) -> dict | None:
    for proj in projects():
        if proj.get("slug") == slug:
            return proj
    return None


def get_collection(slug: str) -> str | None:
    proj = get(slug)
    return proj.get("collection") if proj else None


def get_vault(slug: str) -> str | None:
    proj = get(slug)
    return proj.get("vault") if proj else None


def save(data: dict) -> None:
    """Atomic write (temp + os.replace), mirroring setup_core.write_env, so a
    crash mid-write cannot truncate the registry."""
    p = registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, p)


@contextlib.contextmanager
def _registry_lock():
    """Serialize the registry read-modify-write across concurrent CLI runs (e.g.
    two 'Projekt hinzufügen' launchers at once), so an append cannot be lost when
    both load the same base and the second save() clobbers the first (MP-F04).
    Best-effort: if file locking is unavailable (non-POSIX), proceed without it."""
    p = registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:
        yield
        return
    f = open(p.with_suffix(".lock"), "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


def _unique_slug(name: str, taken: set[str]) -> str:
    slug = slugify(name)
    if slug not in taken:
        return slug
    i = 2
    while f"{slug}_{i}" in taken:
        i += 1
    return f"{slug}_{i}"


def register(name: str, host_path: str, base_collection: str, *,
             vault: str = "", profile: str = "", llm_model: str = "",
             llm_base_url: str = "", created_at: str = "") -> dict:
    """Add a project and return its record. Raises ValueError on a bad path.
    The slug is made unique against existing projects."""
    ok, msg = validate_host_path(host_path)
    if not ok:
        raise ValueError(msg)
    with _registry_lock():
        data = load()
        taken = {p.get("slug") for p in data["projects"]}
        slug = _unique_slug(name, taken)
        record = {
            "slug": slug,
            "name": str(name).strip() or slug,
            "host_path": normalize_host_path(host_path),
            "vault": vault or f"/projects/{slug}",
            "collection": collection_for(base_collection, slug),
            "profile": profile,
            "llm_model": llm_model,
            "llm_base_url": llm_base_url,
            "created_at": created_at,
        }
        data.setdefault("projects", []).append(record)
        save(data)
    return record


def remove(slug: str) -> bool:
    """Drop a project from the registry (does NOT touch its files or its Qdrant
    collection — those are handled, with confirmation, by the caller)."""
    with _registry_lock():
        data = load()
        before = len(data.get("projects", []))
        data["projects"] = [p for p in data.get("projects", []) if p.get("slug") != slug]
        if len(data["projects"]) != before:
            save(data)
            return True
        return False


def synthesize_default(host_path: str, collection: str, *,
                       vault: str = "/vault", created_at: str = "") -> dict:
    """Migrate a legacy single-project install into a 'default' record that
    REUSES its existing collection + vault VERBATIM — so the user's data and
    connector survive the upgrade with no re-embed. No-op if 'default' exists."""
    with _registry_lock():
        data = load()
        existing = get("default")
        if existing:
            return existing
        # Name the default after its folder (e.g. "Test Projekt 1"), so once a
        # second project is added its connector is "brag-<folder>" too — symmetric
        # with the extra projects instead of a bare, unlabelled "brag".
        name = Path(normalize_host_path(host_path or "")).name or "BRAG"
        record = {
            "slug": "default",
            "name": name,
            "host_path": normalize_host_path(host_path or ""),
            "vault": vault,
            "collection": collection,
            "profile": "",
            "llm_model": "",
            "llm_base_url": "",
            "created_at": created_at,
        }
        data.setdefault("projects", []).insert(0, record)
        save(data)
    return record
