# Backend-Profile — welches passt zu dir?

**🇬🇧 [English](PROFILES.md) | 🇩🇪 Deutsch**

Das Profil entscheidet, **welche KI die Textarbeit erledigt** — die 1–2 Sätze
Kontext pro Abschnitt beim Indexieren, die Abbildungsbeschreibungen und die
Dokumentklassifikation. Du wählst es einmal beim Setup und kannst später
wechseln.

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
- *„Meine Dokumente sind vertraulich und ich habe einen starken Mac."* → **Hybrid**
- *„Vertrauliche Dokumente, unter Windows/Linux oder auf einem älteren Mac."* → **Lokal**

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
Macher dieser App oder an Dritte gesendet. Die lokalen Profile weiter unten
brauchen gar keinen Schlüssel.

Der kostenlose Gemini-Tarif deckt einen gleichmäßigen persönlichen Gebrauch ab;
umfangreiches Masseneinlesen kann an Tageslimits stoßen (das System wartet und
versucht es automatisch erneut). OpenAI und Anthropic rechnen pro Token ab — die
oben genannten günstigsten Modelle halten das für einen typischen Korpus bei
wenigen Cent.

## Lokale LLM-Profile (nichts verlässt den Rechner)

| | **Hybrid** (Apple-Silicon-Mac) | **Lokal** (plattformübergreifend) |
|---|---|---|
| Text-LLM | dein Modell in [LM Studio](https://lmstudio.ai) | dein Modell über [Ollama](https://ollama.com) (Standard `llama3.1`) |
| Voraussetzung | LM Studio läuft auf dem Host mit geladenem Modell | Ollama installiert; einmal `ollama pull llama3.1` |
| Hardware | M-Mac, 32 GB RAM empfohlen | mind. 16 GB RAM; eine GPU hilft sehr |
| Datenschutz | nichts verlässt den Rechner | nichts verlässt den Rechner |

Du lädst **kein** Embedding-Modell — arctic läuft eigenständig im Container. Die
App läuft in Docker und erreicht LM Studio / Ollama auf dem Host über
`host.docker.internal` (Port 1234 / 11434).

## Mischen (für Fortgeschrittene)

Jede Komponente lässt sich in der `.env` einzeln überschreiben. Der Hauptgrund
dafür: **schnelle Cloud-Embeddings** auf schwacher Hardware mit großem Korpus —
setze `EMBEDDING_BACKEND=gemini` (oder `openai`) mit passendem `EMBEDDING_MODEL`
/ `EMBEDDING_DIM`. Beachte: Das ist die einzige Änderung, die ein einmaliges
Neu-Einlesen *erfordert* (in eine separate Collection, sicher gehandhabt). Siehe
`.env.example`.
