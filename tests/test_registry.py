"""Unit tests for the multi-project registry (brag.registry)."""

import json

import pytest

from brag import registry


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    yield


def test_slugify_rules():
    assert registry.slugify("ProjektA") == "projekta"
    assert registry.slugify("My Project 2024!") == "my_project_2024"
    assert registry.slugify("  Über/Acht  ") == "ueber_acht"  # umlauts -> ASCII
    assert registry.slugify("Forschung & Lehre") == "forschung_lehre"
    assert registry.slugify("---") == "project"  # never empty


def test_collection_keeps_base_prefix():
    base = "asb_local_st_1024"
    assert registry.collection_for(base, "projekta") == "asb_local_st_1024__projekta"
    # the asb_ prefix must survive so orphan detection still recognizes it
    assert registry.collection_for(base, "x").startswith("asb_")


def test_validate_and_normalize_host_path():
    for bad in ["D:/a$b", "C:/x&y", "C:/p%q", "C:/p^q", "C:/p!q", "", "   "]:
        ok, _ = registry.validate_host_path(bad)
        assert ok is False
    ok, _ = registry.validate_host_path("D:/Arbeit/Projekt A")  # spaces are fine
    assert ok is True
    assert registry.normalize_host_path("D:\\Arbeit\\ProjektA\\") == "D:/Arbeit/ProjektA"


def test_load_missing_returns_empty():
    data = registry.load()
    assert data["projects"] == []
    assert data["version"] == registry.SCHEMA_VERSION


def test_load_corrupt_degrades(tmp_path, monkeypatch):
    p = tmp_path / "projects.json"
    p.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("BRAG_REGISTRY", str(p))
    assert registry.load()["projects"] == []  # never raises


def test_register_builds_record_and_dedups_slug():
    a = registry.register("ProjektA", "D:\\Arbeit\\ProjektA", "asb_local_st_1024")
    assert a["slug"] == "projekta"
    assert a["host_path"] == "D:/Arbeit/ProjektA"
    assert a["collection"] == "asb_local_st_1024__projekta"
    assert a["vault"] == "/projects/projekta"
    # same display name -> a unique slug, not a collision
    b = registry.register("ProjektA", "C:/Else/ProjektA", "asb_local_st_1024")
    assert b["slug"] == "projekta_2"
    assert {p["slug"] for p in registry.projects()} == {"projekta", "projekta_2"}


def test_register_rejects_bad_path():
    with pytest.raises(ValueError):
        registry.register("Bad", "D:/has$dollar", "asb_local_st_1024")


def test_get_and_remove():
    registry.register("ProjektA", "D:/A", "asb_local_st_1024")
    assert registry.get_collection("projekta") == "asb_local_st_1024__projekta"
    assert registry.get_vault("projekta") == "/projects/projekta"
    assert registry.remove("projekta") is True
    assert registry.get("projekta") is None
    assert registry.remove("projekta") is False  # already gone


def test_synthesize_default_reuses_existing_collection():
    rec = registry.synthesize_default("D:/Old/Vault", "asb_local_st_1024")
    assert rec["slug"] == "default"
    assert rec["collection"] == "asb_local_st_1024"   # VERBATIM, no __slug -> no re-embed
    assert rec["vault"] == "/vault"
    # idempotent + inserted first
    again = registry.synthesize_default("D:/Old/Vault", "asb_local_st_1024")
    assert again["slug"] == "default"
    assert registry.projects()[0]["slug"] == "default"


def test_save_is_atomic_and_readable():
    registry.register("P", "D:/P", "asb_x_1")
    raw = json.loads((registry.registry_path()).read_text(encoding="utf-8"))
    assert raw["version"] == registry.SCHEMA_VERSION
    assert raw["projects"][0]["name"] == "P"


class _FakeColl:
    def __init__(self, name):
        self.name = name


class _FakeCollections:
    def __init__(self, names):
        self.collections = [_FakeColl(n) for n in names]


class _FakeClient:
    def __init__(self, names):
        self._names = names

    def get_collections(self):
        return _FakeCollections(self._names)


def test_orphaned_collections_is_registry_aware(monkeypatch):
    from brag import config, storage
    # Monkeypatch the REAL module attr that COLLECTION_NAME resolves to, not the
    # PEP-562 __getattr__-served name itself: setattr(config, "COLLECTION_NAME", …)
    # leaks a static attribute that permanently shadows __getattr__ for every later
    # test (monkeypatch "restores" the dynamic value as a static one).
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_local_st_1024")
    # a registered sibling project must NOT be flagged as a droppable orphan
    registry.register("ProjektA", "D:/A", "asb_local_st_1024")  # -> ...__projekta
    client = _FakeClient([
        "asb_local_st_1024",            # active default
        "asb_local_st_1024__projekta",  # sibling project
        "asb_old_768",                  # genuine leftover from an old embedding
        "some_other_collection",        # non-asb, ignored
    ])
    orphans = storage.orphaned_collections(client)
    assert orphans == ["asb_old_768"]


def test_registry_register_is_concurrency_safe(tmp_path, monkeypatch):
    # Concurrent registrations must not lose an append (MP-F04): the file lock
    # serializes the read-modify-write so every project lands.
    import threading
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    threads = [threading.Thread(target=registry.register,
                                args=(f"Project {i}", f"/host/{i}", "asb_x_1024"))
               for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(registry.projects()) == 8


def test_remove_keeps_the_shared_base_collection(tmp_path, monkeypatch, capsys):
    # `remove --delete-index` on the default project must NOT drop the bare base
    # collection (shared with the single-project fallback) (MP-F08).
    from brag import projects
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    registry.synthesize_default("/host/x", "asb_local_st_1024")   # default → base
    registry.register("Thesis", "/host/thesis", "asb_local_st_1024")  # → ...__thesis
    rc = projects.cmd_remove("default", delete_index=True)
    assert rc == 0
    assert "shared base collection" in capsys.readouterr().err     # refused, data kept
