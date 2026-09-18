"""A single huge file must not flood the context window.

`_resolve` is the seam: it maps a vault-relative path onto a real file plus its root.
Patching it keeps the test off the real vault without touching config.VAULT (which is
served by a module __getattr__ — see Global Constraints).
"""


def test_a_long_file_is_cut_and_says_so(tmp_path, monkeypatch):
    from brag import config, vault
    datei = tmp_path / "gross.md"
    datei.write_text("x" * 5000, encoding="utf-8")
    monkeypatch.setattr(vault, "_resolve", lambda pfad: (datei, tmp_path, ""))
    monkeypatch.setattr(config, "VAULT_READ_MAX_CHARS", 500, raising=False)

    text = vault.vault_read("gross.md")

    assert len(text) < 1000, "not capped"
    assert "gekürzt" in text, "cut silently — the reader cannot tell something is missing"


def test_zero_means_unlimited(tmp_path, monkeypatch):
    from brag import config, vault
    datei = tmp_path / "gross.md"
    datei.write_text("x" * 5000, encoding="utf-8")
    monkeypatch.setattr(vault, "_resolve", lambda pfad: (datei, tmp_path, ""))
    monkeypatch.setattr(config, "VAULT_READ_MAX_CHARS", 0, raising=False)

    assert len(vault.vault_read("gross.md")) == 5000
