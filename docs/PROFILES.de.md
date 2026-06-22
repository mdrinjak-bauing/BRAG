# Backend-Profile — welches passt zu dir?

**🇬🇧 [English](PROFILES.md) | 🇩🇪 Deutsch**

Das Profil entscheidet, **welche KI die Textarbeit erledigt** — die 1–2 Sätze
Kontext pro Abschnitt beim Indexieren und die Abbildungsbeschreibungen. (Der
Dokumenttyp wird aus dem Ordnerpfad abgeleitet, nicht per LLM.) Du wählst es
einmal beim Setup und kannst später wechseln.

**Der Bedeutungs-Index (die Embeddings) läuft immer lokal**, in jedem Profil
(`snowflake-arctic-embed-l-v2.0`, 1024 Dimensionen, auf der CPU — keine GPU
nötig). Daraus folgt:

- Ein **Wechsel des KI-Anbieters** (Gemini ↔ OpenAI ↔ Claude ↔ lokales LLM)
  erfordert **keine Neu-Indexierung** — jedes Profil schreibt in dieselbe
  Collection.
- Die Embeddings sind **kostenlos** (keine Embedding-API-Kosten), und deine
  Dokument-Vektoren **verlassen den Rechner nie**.

Der Cross-Encoder-Reranker läuft in jedem Profil ohnehin schon lokal auf der
CPU — die Embeddings ebenfalls lokal zu rechnen, ist also konsequent. Der
Kompromiss: Der erste Einlesevorgang lädt das arctic-Modell herunter (~2,3 GB
in den Modell-Cache), und das Masseneinlesen auf einer schwachen CPU ist
langsamer als eine Cloud-Embedding-API es wäre. Der Reranker ist zudem der
größte CPU-Posten *jeder Suche* — auf schwachen Rechnern per `RERANK_PROFILE`
(`off`/`eco`/`balanced`/`full`, Standard `eco`) drosseln oder abschalten; siehe
`.env.example`.

## Schnelle Entscheidungshilfe

- *„Es soll einfach laufen, auf diesem Laptop."* → **Gemini** (kostenloser Tarif)
- *„Ich zahle ohnehin für ChatGPT / Claude und will es nutzen."* → **OpenAI** / **Claude**
- *„Meine Dokumente sind vertraulich und ich will sie lokal verarbeiten."* → **Hybrid**

## Cloud-LLM-Profile (jeder Laptop, API-Schlüssel nötig)

Alle drei nutzen lokale arctic-Embeddings; nur das Text-LLM unterscheidet sich.
Bei einem Cloud-Profil wird der **Text** jedes Abschnitts zur Kontext-Erzeugung
an den Anbieter geschickt — und bei aktivem Vision-Pass (Standard) auch die
Bilder deiner Abbildungen — nie die ganzen Dateien, nie die Embeddings.

| Profil | Text-LLM | Günstigste Voreinstellung | Schlüssel holen |
|---|---|---|---|
| **Gemini** (Standard) | Google Gemini | `gemini-2.5-flash-lite` | <https://aistudio.google.com/apikey> (kostenloser Tarif) |
| **OpenAI** | OpenAI / ChatGPT | `gpt-4o-mini` | <https://platform.openai.com/api-keys> |
| **Claude** | Anthropic Claude | `claude-haiku-4-5` | <https://console.anthropic.com/> |

Dein Schlüssel bleibt auf deinem Rechner: Er wird nur in der lokalen
`.env`-Datei gespeichert (nur für dich lesbar) und dient ausschließlich dazu,
deine eigenen Anfragen beim gewählten Anbieter zu authentifizieren — nie an die
Macher dieser App oder an Dritte gesendet. Das lokale Profil weiter unten
braucht gar keinen Schlüssel.

Der kostenlose Gemini-Tarif deckt einen gleichmäßigen persönlichen Gebrauch ab;
umfangreiches Masseneinlesen kann an Tageslimits stoßen (das System wartet und
versucht es automatisch erneut). OpenAI und Anthropic rechnen pro Token ab — die
oben genannten günstigsten Modelle halten das für einen typischen Korpus bei
wenigen Cent.

## Lokales LLM-Profil (nichts verlässt den Rechner)

| | **Hybrid** (plattformübergreifend) |
|---|---|
| Text-LLM | dein Modell in [LM Studio](https://lmstudio.ai) |
| Voraussetzung | LM Studio läuft auf dem Host mit geladenem Modell |
| Hardware | ~16 GB RAM für ein ~7B-Modell (`qwen2.5-7b-instruct`), 32 GB für ein 14B (`qwen2.5-14b-instruct`), 64 GB+ für ein 27B (`gemma-3-27b-it`) — gib LM Studio den vollständigen Modellpfad aus seinem Modell-Browser (z. B. die Hugging-Face-ID); eine GPU hilft sehr |
| Datenschutz | nichts verlässt den Rechner |

Du lädst **kein** Embedding-Modell — arctic läuft eigenständig im Container. Die
App läuft in Docker und erreicht LM Studio auf dem Host über
`host.docker.internal` (Port 1234). Das lokale Profil heißt in LM Studio
**Hybrid**. Eine Einzelprojekt-Installation registriert einen Connector namens
`brag` (in Claude / LM Studio); sobald du weitere Projekte hinzufügst, bekommt
jedes seinen eigenen beschrifteten Connector — das Standardprojekt wird zu
`brag-<Ordner>` und jedes zusätzliche zu `brag-<Name>`, damit keiner unbeschriftet bleibt.

## Mischen (für Fortgeschrittene)

Jede Komponente lässt sich in der `.env` einzeln überschreiben. Der Hauptgrund
dafür: **schnelle Cloud-Embeddings** auf schwacher Hardware mit großem Korpus —
setze `EMBEDDING_BACKEND=gemini` (oder `openai`) mit passendem `EMBEDDING_MODEL`
/ `EMBEDDING_DIM`. Beachte: Das ist die einzige Änderung, die ein einmaliges
Neu-Einlesen *erfordert* (in eine separate Collection, sicher gehandhabt). Siehe
`.env.example`.

**Datenschutz-Hinweis:** Dieser Override sendet deinen Dokumenttext an den
Embedding-Anbieter (Gemini/OpenAI) — nicht für vertrauliche oder
personenbezogene Inhalte. Für lokal-only beim Standard-Profil-Embedder bleiben.
