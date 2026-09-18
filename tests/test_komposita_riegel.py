"""German compound splitting must not fire on an English corpus."""


def test_english_query_is_untouched(monkeypatch):
    from brag import config
    from brag.embeddings import sparse
    monkeypatch.setattr(config, "VAULT_LANGUAGE", "english", raising=False)
    assert sparse.decompose_compounds("Systematically reviewing the literature") == []


def test_german_query_is_split(monkeypatch):
    from brag import config
    from brag.embeddings import sparse
    monkeypatch.setattr(config, "VAULT_LANGUAGE", "german", raising=False)
    assert "Nachtrag" in sparse.decompose_compounds("Nachtragsmanagement im Bauvertrag")
