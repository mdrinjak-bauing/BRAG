"""Cross-lingual query expansion — appends established English domain terms to a query.

Tabelle zuerst: eine deterministische DE->EN-Fachvokabular-Abbildung (KEIN LLM-Call)
hängt die etablierten englischen Fachbegriffe an eine deutsche Query, damit sie auch
englische Quellen findet. Optionales lokales LLM-Auffangnetz (config
QUERY_EXPANSION_BACKEND="hybrid") füllt Begriffe außerhalb der Tabelle und fällt bei
jedem Fehler still auf das Tabellen-Ergebnis zurück (nichts bricht).

Die Tabelle QUERY_EXPANSION_VOCAB unten ist VERBATIM aus dem lokalen System kopiert.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from brag import config


QUERY_EXPANSION_VOCAB = [
    (["künstliche intelligenz"], "artificial intelligence"),
    (["ki-akzeptanz", "ki-adoption", "ki-annahme"], "AI adoption"),
    (["ki-einführung", "ki-implementierung"], "AI implementation"),
    (["ki-anwendung", "ki-einsatz"], "AI application"),
    (["implementierungsbarrieren", "hemmschuh"], "implementation barriers"),
    (["hürde", "hürden", "hindernis", "hemmnis", "barriere"], "barriers"),
    (["fachwissen", "know-how", "kompetenz"], "expertise"),
    (["halluzination"], "hallucination"),
    (["datenqualität"], "data quality"),
    (["datenvarianz", "datenheterogenität"], "data heterogeneity"),
    (["datenverfügbarkeit"], "data availability"),
    (["trainingsdaten"], "training data"),
    (["retrieval augmented generation"], "retrieval-augmented generation"),
    (["funktionsprinzip"], "operating principle"),
    (["bauausführung"], "construction execution"),
    (["bauunternehmen", "bauunternehmer"], "construction company"),
    (["bauindustrie", "bauwirtschaft", "bauwesen", "baubranche"], "construction industry"),
    (["bauablaufstörung", "behinderung"], "disruption claim"),
    (["nachtragsmanagement", "nachtrag"], "change order"),
    (["mängelmanagement", "mängel"], "defect management"),
    (["bauschäden"], "construction defects"),
    (["qualitätsmanagement", "qualitätssicherung"], "quality management"),
    (["baufortschritt"], "construction progress"),
    (["baustelle"], "construction site"),
    (["bauprozess", "bauablauf"], "construction process"),
    (["vergütung", "honorar"], "remuneration fee"),
    (["vergabe"], "procurement tender"),
    (["bauinvestitionen"], "construction investments"),
    (["arbeitsplanung"], "work planning"),
    (["kleine und mittlere unternehmen", "kmu", "kleine unternehmen"], "SMEs"),
    (["beschäftigte", "mitarbeiter"], "employees workforce"),
    (["fach- und führungskräfte", "fachkräfte", "führungskräfte"], "professionals"),
    (["hochrisiko-ki"], "high-risk AI"),
    (["dsgvo"], "GDPR"),
    (["normung", "norm"], "standardization"),
    (["digitalisierung"], "digitalization"),
    (["bim-verbreitung", "bim-akzeptanz"], "BIM adoption"),
    (["fehlend", "mangel an", "mangelnd", "mangelnde"], "lack of"),
    (["akzeptanz"], "adoption"),
    # ── 2026-06-10: korpusbasierter Ausbau (43 EN-Quellen, lokal extrahiert via
    # gemma-4-26b-a4b, kuratiert + bereinigt; Bericht s. CHANGELOG) ──
    (["ablation-test", "ablationsstudie"], "ablation study"),
    (["anpassung an automatisierung", "automatisierungskompetenz"], "adaptation automation"),
    (["aec-sektor"], "AEC sector"),
    (["agenten-produktivität", "skalierung der agenten-produktivität"], "agent productivity scaling"),
    (["ki-framework", "ki-rahmenwerk"], "AI framework"),
    (["aufgabenverteilung", "funktionsallokation"], "allocation function"),
    (["artefakt", "gestaltungsobjekt"], "artefact"),
    (["artefakt", "forschungsartefakt"], "artifact"),
    (["automatisierte vertragsprüfung", "automatisierter contract review"], "Automated contract review"),
    (["automatisierte datenerfassung"], "automated data collection"),
    (["automatisierte bauüberwachung", "digitales monitoring"], "Automated monitoring construction"),
    (["automatisierte qualitätskontrolle", "automatisierung der qualitätsprüfung"], "automated quality control"),
    (["automatisierung"], "automation"),
    (["automatisierungsabhängigkeit", "reliance auf automatisierung"], "automation reliance"),
    (["automatisierte agenten", "autonome agenten"], "autonomous agents"),
    (["evaluationsmaßstab"], "benchmark"),
    (["modell-evaluierung"], "benchmarking"),
    (["benchmark-taxonomie", "evaluierungs-taxonomie"], "benchmarking taxonomy"),
    (["bibliometrie"], "bibliometric analysis"),
    (["materialliste", "stückliste"], "bill materials"),
    (["bim-datenmanagement", "informationsmodellierung"], "BIM data management"),
    (["bim-basierte informationstechnologie"], "BIM information technology"),
    (["bim-basiertes qualitätsmanagement", "digitales qualitätsmanagement im bauwesen"], "BIM-based construction quality management"),
    (["blockchain-basierte lösungen", "blockchain-technologie"], "Blockchain-based technical solution"),
    (["bottom-up-ansatz", "bottom-up-methodik"], "Bottom-up methodology"),
    (["gebäude-ontologie"], "Brick Schema"),
    (["gebäudemodellierung"], "Building Information Modeling"),
    (["bim-modellierung"], "Building Information Modelling"),
    (["gebäudebetriebs-lebenszyklus", "lebenszyklus des gebäudes"], "building's life cycle"),
    (["cloud-basierte ki-angebote", "cloud-ki"], "cloud-based AI offerings"),
    (["kollektives aktionsproblem", "kollektives handeln-problem"], "collective action problem"),
    (["komprimierungsstrategie", "kontextkomprimierung"], "compaction"),
    (["strategischer wettbewerbsvorteil", "wettbewerbsvorteil"], "competitive advantage"),
    (["computergestützte bildverarbeitung", "computergestütztes sehen"], "computer vision"),
    (["konzeptionelle kostenschätzung", "kostenschätzung im bauwesen"], "conceptual cost estimates"),
    (["allgemeine vertragsbedingungen", "besondere vertragsbedingungen", "vertragsbedingungen"], "Conditions contract"),
    (["detektion der konsistenz", "konsistenzprüfung"], "consistency detection"),
    (["bauverträge", "vertragsmanagement im bauwesen"], "Construction Contracts"),
    (["intelligente baustellensicherheit", "ki-gestützte arbeitssicherheit"], "Construction safety"),
    (["bauwesen-kmu", "kleine und mittlere unternehmen im bau"], "Construction SMEs"),
    (["inhalts-einbettung", "semantische einbettung"], "content embedding"),
    (["kontext-präzision"], "context precision"),
    (["kontrastives sprach-bild-lernen"], "contrastive language-image learning"),
    (["beitrag", "forschungsbeitrag"], "contribution"),
    (["chatbots", "konversationsagenten"], "conversational agents"),
    (["faltungsneuronale netze", "konvolutionsneuronale netze"], "convolutional neural network"),
    (["bewältigungsstrategien", "coping-prozesse"], "coping process"),
    (["interkulturelle vergleichsstudie", "querschnittstudie"], "cross-cultural study"),
    (["datenaugmentation", "datenvergrößerung"], "data augmentation"),
    (["daten-governance"], "data governance"),
    (["datenmanagement", "datenverwaltung"], "data management"),
    (["datengestützte strategie", "datengetriebene strategie"], "data-driven strategy"),
    (["entscheidungsunterstützungssystem", "ki-gestützte entscheidungsfindung"], "decision-support tools"),
    (["defekterkennung", "fehlererkennung"], "defect detection"),
    (["dense retrieval", "dichte vektorindizes", "dichte vektorsuche"], "dense vector index"),
    (["dichte vektorabfrage"], "dense vector retrieval"),
    (["design-prinzipien", "gestaltungsprinzipien"], "design principles"),
    (["design-propositionen", "gestaltungsvorschläge"], "design propositions"),
    (["dsr-forschung"], "Design Science Research"),
    (["design-theorie", "entwurfstheorie"], "design theory"),
    (["design science research", "design-science-forschung"], "design-science research"),
    (["design for additive manufacturing", "dfam"], "DfAM domain"),
    (["digitale reife", "digitalisierungsgrad"], "digital maturity"),
    (["digital twin-technologie", "digitaler zwilling"], "Digital twin"),
    (["digitale zwillinge", "digitaler zwilling"], "digital twins"),
    (["digitale transformation im bauwesen", "digitalisierung im baubetrieb"], "digitization construction operations"),
    (["nichtgebrauch von automatisierung", "nichtnutzung"], "disuse"),
    (["domänenadaption", "domänenspezifische anpassung"], "Domain adaptation"),
    (["domänenspezialisierung", "fachspezifische anpassung"], "Domain specialization"),
    (["domänenspezifische wissensextraktion", "domänenspezifisches wissen", "fachbereichsspezifische semantik"], "domain-specific knowledge"),
    (["doppelstimulation", "doppelte stimulation"], "double stimulation"),
    (["end-to-end-feintuning", "end-to-end-training"], "end-to-end fine-tuning"),
    (["entitäten-alignment"], "Entity alignment"),
    (["bewertungskonstrukt", "evaluationskonstrukt"], "evaluation construct"),
    (["benchmarking", "evaluations-framework", "evaluationsrahmen", "modell-evaluierung"], "evaluation framework"),
    (["übereinstimmung mit der referenz"], "exact match"),
    (["austrittsbarrieren", "markteintrittsbarrieren"], "exit cost barriers entry"),
    (["expertenbefragung", "expertengestützte evaluation"], "Expert evaluation"),
    (["expertensysteme", "wissensbasierte systeme"], "expert systems"),
    (["erklärbarkeit", "interpretierbarkeit"], "explainability"),
    (["erklärbare ki", "explainable ai"], "explainable AI"),
    (["erklärungsgehalt", "erklärungskraft"], "Explanatory power"),
    (["extrahierende frage-antwort-systeme", "extraktive beantwortung"], "extractive question answering"),
    (["faktenbasierte verifizierung", "faktencheck"], "fact checking"),
    (["faktenbasierte verlässlichkeit", "faktentreue"], "Factual reliability"),
    (["faktentreue", "faktizität"], "factuality"),
    (["schadenserkennung"], "fault detection"),
    (["few-shot-beispiele", "few-shot-learning"], "few-shot examples"),
    (["beispielbasiertes lernen"], "few-shot learning"),
    (["fidic-formulare", "fidic-vertragsbedingungen"], "FIDIC Conditions Contract"),
    (["fidic-modellverträge", "fidic-vertragsbedingungen"], "FIDIC contract conditions"),
    (["feldproblem", "problemstellung in der praxis"], "field problem"),
    (["feldtest", "praxistest"], "field tested"),
    (["feinabstimmung"], "Fine-tuning"),
    (["erste-ordnung-logik", "prädikatenlogik"], "first-order logical rules"),
    (["grundriss-objekterkennung", "grundrisserkennung"], "floor plan object detection"),
    (["formativ-evaluative untersuchung"], "formative evaluation"),
    (["basismodelle", "grundlagenmodelle"], "foundation models"),
    (["fuzzy-logik", "fuzzy-neuronale netze"], "Fuzzy Neural Inference Model"),
    (["genai", "generative ki", "generative künstliche intelligenz"], "Generative AI"),
    (["generative sprachmodelle", "large language models"], "generative large language models"),
    (["graph-neuronale netze"], "graph neural networks"),
    (["goldstandard", "referenzdaten"], "ground truth"),
    (["halluzinationsdichte"], "hallucination density"),
    (["detektion von halluzinationen", "halluzinationserkennung"], "hallucination detection"),
    (["halluzinationen in sprachmodellen", "modellhalluzination"], "Hallucination large language models"),
    (["halluzination-mitigation", "halluzinationsminderung"], "hallucination mitigation"),
    (["halluzinationen", "modell-halluzinationen"], "hallucinations"),
    (["automatisierte gefahrenerkennung"], "Hazard recognition"),
    (["mensch-computer-interaktion", "mensch-ki-kollaboration"], "human-AI collaboration"),
    (["mensch-maschine-interaktion"], "human-in-the-loop"),
    (["mensch-computer-interaktion", "mensch-maschine-interaktion"], "human-machine interaction"),
    (["hybride ki", "hybride ki-systeme"], "hybrid AI systems"),
    (["digitalisierungsgrad", "industrie 4.0-reifegrad"], "Industry 4.0 readiness"),
    (["informationsasymmetrie", "informationsungleichgewicht"], "information asymmetry"),
    (["digitale bauinformation", "informationsmodell"], "information model"),
    (["informationssysteme", "is-forschung"], "Information Systems"),
    (["informationssystem-forschung", "informationssystemforschung", "is-forschung"], "information systems research"),
    (["informationssystem-erfolg", "is-erfolg"], "Information Systems Success"),
    (["einbettung", "embedding-verfahren", "vektorisierung"], "Information vectorization"),
    (["automatisierte bauplanung", "intelligentes designmanagement"], "intelligent design management"),
    (["interventionsforschung"], "interventionist researchers"),
    (["jailbreak-angriffe", "prompt-injection"], "jailbreak attacks"),
    (["arbeitsplatzgefahrenanalyse", "gefahrenanalyse"], "job hazard analysis"),
    (["kendall-koeffizient der übereinstimmung", "kendall-konkordanzkoeffizient"], "Kendall's coefficient concordance"),
    (["kg-vektor-ansatz", "wissensgraph-vektor-methode"], "KG-Vector approach"),
    (["alignment mit wissensbasen", "wissensdatenbank-abgleich"], "knowledge base alignment"),
    (["wissensmodellierung"], "knowledge engineering"),
    (["wissensgraph-konstruktion"], "Knowledge Graph Construction"),
    (["wissensgraph-einbettung"], "knowledge graph embedding"),
    (["wissensgraph"], "knowledge graphs"),
    (["wissensbasis", "wissenspool"], "knowledge pool"),
    (["wissensgestützte sprachmodelle"], "Knowledge-augmented language models"),
    (["wissensbasierte entscheidungsunterstützung"], "knowledge-enhanced decision support"),
    (["logisches schließen", "wissensbasierte logik"], "knowledge-enhanced logical reasoning"),
    (["große sprachmodelle", "großsprachmodelle", "llms"], "large language models"),
    (["latente variable", "latente variablen"], "latent variable"),
    (["llm-guardrails", "sicherheitsleitplanken für llms"], "LLM guardrails"),
    (["llm als richter", "modell-basierte evaluation"], "LLM-as-a-judge"),
    (["long-context-modelle", "modelle mit langem kontext"], "Long context"),
    (["langfristige aufgaben", "langzeithorizont-aufgaben"], "long-horizon tasks"),
    (["longitudinal-vergleich", "längsschnittanalyse"], "longitudinal comparison"),
    (["ressourcenarme sprachen"], "low-resource languages"),
    (["maschinelles lernen", "ml-methoden"], "machine learning methods"),
    (["markov-logik-netzwerke"], "Markov logic networks"),
    (["master-datenmodell", "stammdatenmodell"], "master data model"),
    (["mips-suche"], "Maximum Inner Product Search"),
    (["mechanismen", "wirkungsmechanismus"], "mechanism"),
    (["mechanistische interpretationsfähigkeit", "mechanistische interpretierbarkeit"], "Mechanistic interpretability"),
    (["mid-range-theory", "theorie auf mittlerer ebene"], "mid-range theory"),
    (["fehlbedienung", "missbrauch von automatisierung"], "misuse"),
    (["modellgröße", "modellskalierung"], "model scale"),
    (["moderatoreffekt", "moderierende wirkung"], "Moderating effect"),
    (["multi-agenten-systeme"], "multi-agent systems"),
    (["mehrstufige schlussfolgerung", "mehrstufiges logisches schließen", "multi-hop-reasoning"], "multi-hop reasoning"),
    (["n-gramm", "n-gramme"], "n-gram"),
    (["natürliche sprachverarbeitung"], "Natural Language Processing"),
    (["naturalistische evaluation", "natürliche evaluation"], "naturalistic evaluation"),
    (["nichtparametrische statistik", "nichtparametrisches verfahren"], "Non-parametric approach"),
    (["nicht-parametrische wissensbasis", "nicht-parametrischer speicher"], "non-parametric memory"),
    (["normen-alignment", "normenausrichtung"], "norm-alignment"),
    (["objekterkennung", "objektidentifikation"], "object detection"),
    (["modulbau", "vorfertigung"], "Off-site production Modular construction"),
    (["ontologieschema-konstruktion", "schema-extraktion"], "Ontology schema construction"),
    (["ontologie-basierte wissensrepräsentation", "owl 2 dl ontologien"], "ontology-based knowledge representation"),
    (["ontologie-gestützte abfrage", "ontologiebasierte abfragen"], "ontology-based queries"),
    (["offene informationsextraktion"], "Open information extraction"),
    (["betrieb und instandhaltung", "instandhaltung und wartung"], "operation maintenance phase"),
    (["paarweiser vergleich", "pairwise evaluation"], "pairwise fashion"),
    (["parametrische wissensbasis", "parametrischer speicher"], "parametric memory"),
    (["pareto-optimale entscheidungen", "pareto-optimalität"], "Pareto optimal"),
    (["patch-merging", "zusammenführung von korrekturen"], "patch merging"),
    (["pfadanalyse", "strukturgleichungsmodellierung"], "path analysis"),
    (["hierarchische pfade", "pfad-einbettungen", "wissenshierarchie"], "path features"),
    (["ease of use", "wahrgenommene benutzerfreundlichkeit"], "Perceived Ease Use"),
    (["handhabungsfreundlichkeit", "wahrgenommene benutzerfreundlichkeit"], "Perceived ease-of-use"),
    (["wahrgenommene repräsentation", "wahrgenommene repräsentationsfähigkeit"], "Perceived Representation"),
    (["subjektive nützlichkeit", "wahrgenommene nützlichkeit"], "Perceived usefulness"),
    (["plausibilitätscheck", "plausibilitätsprüfung"], "plausibility checking"),
    (["kontextbezogene plausibilität", "plausible halluzinationen"], "plausible hallucination"),
    (["fünf-kräfte-modell"], "Porter's five forces"),
    (["prädiktive analytik", "vorausschauende analysen"], "predictive analytics"),
    (["prädiktive instandhaltung", "vorausschauende instandhaltung", "vorausschauende wartung"], "predictive maintenance"),
    (["prädiktive qualitätsanalyse", "vorausschauende qualitätsanalyse"], "predictive quality analysis"),
    (["proaktives qualitätsmanagement", "vorausschauendes qualitätsmanagement"], "proactive quality management"),
    (["probabilistische schaltkreise"], "probabilistic circuits"),
    (["probabilistische grafische modelle"], "probabilistic graphical models"),
    (["probabilistische inferenz", "prädiktive inferenz"], "probabilistic inference"),
    (["prozesseffizienz", "prozessoptimierung"], "process efficiency"),
    (["prozess-virtualisierbarkeit", "virtualisierbarkeit von prozessen"], "Process Virtualizability"),
    (["prozess-virtualisierung", "prozessvirtualisierung"], "Process Virtualization"),
    (["prozesskontrolle", "prozesssteuerung"], "Process-control management"),
    (["marktdifferenzierung", "produktdifferenzierung"], "product differentiation"),
    (["einfluss auf die produktivität", "produktivitätssteigerung"], "Productivity impact"),
    (["kostenmanagement im bauwesen", "projektkostenmanagement"], "Project Cost Management"),
    (["prompt-optimierung"], "prompt engineering"),
    (["prompt-multiplizität", "vielfalt der prompts"], "prompt multiplicity"),
    (["prompt-sensitivität", "reaktionssensitivität auf prompts"], "prompt sensitivity"),
    (["digitalisierte qualitätssicherung", "qualität 4.0"], "Quality 4.0"),
    (["qualitätskontrolle"], "quality assurance"),
    (["baubetriebliche qualitätskontrolle", "qualitätssicherung im bauwesen"], "quality control built environment"),
    (["aufmaß", "massenermittlung", "mengenermittlung"], "quantity determination"),
    (["bauökonom"], "Quantity Surveyor"),
    (["rag-systeme", "retrieval-augmented generation"], "RAG settings"),
    (["rag-strategien", "retrieval-augmented generation"], "RAG strategies"),
    (["regressionsgefährdung", "regressionsrisiko"], "regression risks"),
    (["regulator-agent", "steuerungsagent"], "regulator agent"),
    (["compliance", "einhaltung von vorschriften", "regelkonformität"], "regulatory compliance"),
    (["bestärkendes lernen"], "Reinforcement Learning"),
    (["relevanz-voting", "stimmabgabe-strategie"], "relevance voting strategy"),
    (["abrufgestützte generierung", "rag-verfahren"], "Retrieval Augmented Generation"),
    (["it-investitionsrendite", "return on investment von informationstechnologie"], "returns investments information technology"),
    (["methodische strenge", "stringenz"], "rigor"),
    (["risikoanalyse", "risikomanagement", "risikosteuerung"], "Risk management"),
    (["längste gemeinsame teilsequenz", "rouge-l metrik"], "ROUGE-L metric"),
    (["kontextmanagement", "laufzeit-kontextmanagement"], "runtime context management"),
    (["risikomanagement-leitfaden", "sicherheitsmanagement-anweisungen"], "safety risk management guidance"),
    (["skalierungsgesetze"], "scaling laws"),
    (["dynamische schema-evolution", "schema-adaption"], "Schema adaptation"),
    (["forschungsmethodik der scientometrie"], "scientometric analysis"),
    (["pattern induction", "semantische musterinduktion"], "Semantic pattern induction"),
    (["automatisierte schlussfolgerung", "semantisches schließen"], "semantic reasoning"),
    (["sensorische anforderungen", "wahrgenommene sensorische anforderungen"], "Sensory Requirements"),
    (["seq2seq-modell", "sequenz-zu-sequenz-modelle"], "seq2seq model"),
    (["gemeinsames objekt", "geteilter gegenstand"], "shared object"),
    (["situative kognition", "situierte kognition"], "situated cognition"),
    (["intelligente bautechnik"], "smart construction"),
    (["automatisierte sparql-erstellung", "sparql-abfragegenerierung"], "SPARQL query generation"),
    (["spearman-rangkorrelation", "spearmans korrelationskoeffizient"], "Spearman's correlations"),
    (["strategische informationsverarbeitung", "strategisches informationsmanagement"], "strategic information processing"),
    (["modellgestützte zusammenfassung", "zusammenfassung"], "summarization"),
    (["summativ-evaluative untersuchung"], "summative evaluation"),
    (["lieferkettenoptimierung", "supply-chain-optimierung"], "supply chain optimization"),
    (["nachhaltigkeitsmessung", "nachhaltigkeitsmetrik"], "sustainability measurement"),
    (["synthetische datengenerierung"], "synthetic data generation"),
    (["synthetische abfragen", "synthetische queries"], "synthetic queries"),
    (["systematischer drift"], "systemic drift"),
    (["aufgaben-technologie-passung", "task-technology-fit"], "Task-Technology Fit"),
    (["techno-stressoren", "technologische stressfaktoren"], "techno-stressors"),
    (["akzeptanz von technologien", "technologieakzeptanz"], "technology acceptance"),
    (["tam-modell", "technologieakzeptanzmodell", "technology acceptance model"], "Technology Acceptance Model"),
    (["annahme neuer technologien", "technologieakzeptanz"], "Technology adoption"),
    (["technostress-belastung"], "technostress"),
    (["einbettungsmodelle", "text-embedding-modelle"], "text embedding models"),
    (["text-mining", "text-mining-verfahren"], "Text mining"),
    (["automatisierte textsummarisierung", "textzusammenfassung"], "Text summarization"),
    (["tool-basierte evidenz", "werkzeuggestützte evidenz"], "tool-mediated evidence"),
    (["total-quality-management", "umfassendes qualitätsmanagement"], "Total Quality Management"),
    (["tragik der allmende"], "tragedy commons"),
    (["transformer-architektur", "transformer-modelle"], "Transformer"),
    (["abschneiden", "textkürzung"], "truncation"),
    (["automatisierungsvertrauen", "vertrauen in automatisierungssysteme"], "trust automation"),
    (["vertrauenswürdige ki"], "trustworthy AI"),
    (["unstrukturierte berichte", "unstrukturierte unfalldaten"], "unstructured accident data"),
    (["anwenderakzeptanz", "nutzerakzeptanz"], "User Acceptance"),
    (["anwendungsnutzen", "nutzen", "nützlichkeit"], "utility"),
    (["nutzungsverhalten", "systemnutzung"], "Utilization"),
    (["varianzmodell", "varianztheorie"], "variance theory"),
    (["vektorbasierte datenbanken", "vektordatenbank"], "Vector database"),
    (["gebäudelebenszyklus", "lebenszyklus von gebäuden"], "whole life cycle buildings"),
    (["arbeitsaktivität", "arbeitsaktivitätssystem"], "work activity"),
    (["nullschuss-fragebeantwortung"], "zero-shot question answering"),

]


_QE_PAIRS = sorted(
    [(v.lower(), en) for variants, en in QUERY_EXPANSION_VOCAB for v in variants],
    key=lambda kv: -len(kv[0]),
)

_QE_STRIP_CHARS = ".,;:" + '"' + "'" + "()"


def _expand_query_local(query: str) -> str | None:
    """Deterministische, tabellenbasierte DE->EN-Expansion (KEIN LLM). Längste
    DE-Begriffe zuerst, gematchte Spans werden geblankt (damit kürzere Überlapper sie
    nicht erneut matchen), max. 12 Zusatz-Tokens. Verbatim aus dem lokalen System."""
    work = query.lower()
    qlow = query.lower()
    added: list[str] = []
    added_low: set[str] = set()
    for de, en in _QE_PAIRS:
        if de in work:
            work = work.replace(de, " " * len(de))
            for term in en.split():
                tl = term.lower()
                if tl not in qlow and tl not in added_low:
                    added.append(term)
                    added_low.add(tl)
    if not added:
        return None
    added = added[:12]
    return query + " " + " ".join(added)


_QE_LLM_PROMPT = (
    "Übersetze die folgende deutsche Suchanfrage eines Bauingenieurs in das "
    "etablierte ENGLISCHE Fachvokabular der internationalen Construction-Management-/"
    "KI-Literatur (akademische Standardbegriffe, KEINE Wort-für-Wort-Übersetzung; "
    "z.B. Hürden→barriers, KI-Akzeptanz→AI adoption, KMU→SMEs).\n"
    "Antworte NUR mit 3-8 englischen Suchbegriffen, durch Leerzeichen getrennt, "
    "ohne Erklärungen, ohne Anführungszeichen.\n\n"
    "Suchanfrage: {query}"
)

_QE_CACHE_PATH = Path.home() / ".cache" / "brag" / "qe_llm_cache.json"
_qe_llm_cache = None


def _qe_cache_load() -> dict:
    global _qe_llm_cache
    if _qe_llm_cache is None:
        try:
            _qe_llm_cache = json.loads(_QE_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            _qe_llm_cache = {}
    return _qe_llm_cache


def _expand_query_llm(query: str) -> str | None:
    """Englische Zusatzbegriffe vom aktiven LLM-Backend (gecacht). Gibt bei JEDEM
    Fehler None zurück -> Aufrufer fällt auf das Tabellen-Ergebnis zurück (nichts bricht)."""
    cache = _qe_cache_load()
    key = " ".join(query.lower().split())
    if key in cache:
        return cache[key] or None
    raw = None
    try:
        from brag.llm_backends import get_llm
        raw = get_llm().chat(_QE_LLM_PROMPT.format(query=query), max_tokens=200)
    except Exception:
        raw = None
    terms = None
    if raw:
        toks = [t.strip(_QE_STRIP_CHARS) for t in raw.split()]
        toks = [t for t in toks if 3 <= len(t) <= 30 and re.fullmatch(r"[A-Za-z][A-Za-z-]*", t)]
        if toks:
            terms = " ".join(dict.fromkeys(toks))[:200]
    cache[key] = terms or ""
    try:
        _QE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _QE_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    except Exception:
        pass
    return terms


def _expand_query_hybrid(query: str) -> str | None:
    """Tabelle (0 ms) + LLM-Auffangnetz, wenn die Tabelle weniger als
    config.QE_HYBRID_MIN_TERMS Zusatzbegriffe liefert."""
    table_result = _expand_query_local(query)
    n_table_terms = len(table_result.split()) - len(query.split()) if table_result else 0
    if n_table_terms >= config.QE_HYBRID_MIN_TERMS:
        return table_result
    llm_terms = _expand_query_llm(query)
    if not llm_terms:
        return table_result
    base = table_result or query
    base_low = base.lower()
    extra = [t for t in llm_terms.split() if t.lower() not in base_low]
    if not extra:
        return table_result
    return base + " " + " ".join(extra[:10])


def expand_query(query: str) -> str | None:
    """Cross-lingual-Expansion-Dispatch, spiegelt das lokale System:
    'off' | 'local' (nur Tabelle) | 'hybrid' (Tabelle + LLM-Auffangnetz, graceful).
    Das Ergebnis (wenn nicht None) beginnt IMMER mit der Original-Query (Zusatzbegriffe
    werden angehängt) — das Sprach-Gate in search() verlässt sich darauf."""
    backend = (config.QUERY_EXPANSION_BACKEND or "off").lower()
    if backend == "off":
        return None
    if backend == "hybrid":
        return _expand_query_hybrid(query)
    return _expand_query_local(query)
