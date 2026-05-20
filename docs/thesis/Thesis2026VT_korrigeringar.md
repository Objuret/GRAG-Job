# Korrigeringsdokument: Thesis2026VT.pdf ↔ faktisk implementation

**Syfte:** Detta dokument jämför uppsatsen *Thesis2026VT.pdf* med repot `exjobbet/repo` och ger **färdig ersättningstext på svenska** där texten idag är fel, missvisande eller ofärdig. Resultat av export/RAGAS är **inte slutgiltiga** — kapitel 7 använder därför **platshållare** enligt schema nedan.

**Källor:** Kod (`backend/tagging/`, `frontend/src/services/`, `ragas-export.ts`), `docs/backend/status.md`, `docs/backend/ragas_eval_report.md`, `docs/graph_schema.md`.

**Senast uppdaterad:** 2026-05-20.

**Relaterade dokument:**

| Dokument | Innehåll |
|----------|----------|
| [`Thesis2026VT_kap6_ersattningstext.md`](Thesis2026VT_kap6_ersattningstext.md) | **Kopiera-klistra-in** hela kap. 6 till Word (svenska, en sida) |
| [`Thesis2026VT_corrections_EN.md`](Thesis2026VT_corrections_EN.md) | **Engelsk parallell** (metod, fel, platshållare kap. 7) |
| [`repo_truth_comprehensive.md`](repo_truth_comprehensive.md) | **Hela kodbas-analysen** (lång form, kod-verifierad) |
| [`thesis_pdf_vs_reality.md`](thesis_pdf_vs_reality.md) | **Hela PDF-jämförelsen** med felmarkeringar |
| [`README.md`](README.md) | Index över alla thesis-dokument |

---

## Platshållare (resultat — fyll i när export/RAGAS är klar)

| Platshållare | Betydelse | Var det kommer från |
|--------------|-----------|---------------------|
| `[N_GOLD]` | Antal gold-frågor (t.ex. 100) | `ragas-questions.herb-gold100.jsonl` |
| `[N_GRAPH_OK]` | Antal graph-armar med svar utan `meta.error` | `A_tags.jsonl` efter dedupe |
| `[N_BASE_OK]` | Antal baseline-armar med svar utan `meta.error` | `B_baseline.jsonl` |
| `[MEDIAN_*]` | Median per mått | `A_tags.report.json` / `B_baseline.report.json` |
| `[IQR_*]` | IQR per mått | samma |
| `[DELTA_*]` | Skillnad graph − baseline | beräknat |
| `[PILOT_NOTE]` | Kort not om exportfel/timeouts | `ragas_eval_report.md` |

**Exempel när klart:** ersätt platshållare med värden i tabellen nedan (2026-05-20).

### Ifyllda värden (2026-05-20, `ragas_exports/*.report.json`)

Källa: [`docs/backend/ragas_eval_report.md`](../backend/ragas_eval_report.md). Rapporterna committas inte (gitignore); siffrorna är kopierade hit för Word.

| Platshållare | Värde |
|--------------|-------|
| `[N_GOLD]` | 100 |
| `[N_GRAPH_OK]` | 92 |
| `[N_BASE_OK]` | 95 |
| `[MODELL_SVAR]` / `[MODELL_JUDGE]` | deepseek-chat |
| `[MEDIAN_FA_GRAPH]` / `[IQR_FA_GRAPH]` | 0,81 (0,58–1,00) |
| `[MEDIAN_FA_BASE]` / `[IQR_FA_BASE]` | 0,80 (0,61–1,00) |
| `[MEDIAN_CR_GRAPH]` / `[IQR_CR_GRAPH]` | 0,86 (0,00–1,00) |
| `[MEDIAN_CR_BASE]` / `[IQR_CR_BASE]` | 1,00 (0,00–1,00) |
| `[MEDIAN_CP_GRAPH]` / `[IQR_CP_GRAPH]` | 0,00 (0,00–0,03) |
| `[MEDIAN_CP_BASE]` / `[IQR_CP_BASE]` | 0,00 (0,00–0,05) |
| RAGAS `n` (faithfulness) | graph 92, baseline 94 |
| RAGAS `n` (context_recall) | graph 91, baseline 95 |

**Föreslagen `[SAMMANFATTNING_EFTER_SIFFROR]`:** baseline besvarade fler frågor (95 vs 92) och hade högre median context_recall (1,00 vs 0,86); faithfulness var i stort sett lika (median 0,80 vs 0,81). Skillnaderna ska läsas tillsammans med exportfel, ogiltig gate och låg context_precision — inte som generell överlägsenhet för någon arm.

---

## Snabbreferens: vad som faktiskt byggts

| Aspekt | Uppsatsen antyder ofta | Verklighet i repot |
|--------|------------------------|-------------------|
| Domän | Bonnier-artiklar, journalister | **Salesforce HERB** (produkter, Slack, PR, dokument, QA) |
| Data | Flera databaser | **En** korpus → **Neo4j** (`herb`, eval: `herb-eval`) |
| Tagging | Ett LLM-anrop: beskrivning + taggar | **Tvåpass** Anthropic `extract` + `describe` + `score` |
| Vektorer | Utanför scope | **e5** på `:Tag.emb_*` — **obligatoriskt** för graph-retrieval |
| Graph-retrieval | Graftraversal, multi-hop | **kNN på taggar** + viktad **`HAS_TAG`** + gate; ev. fulltext-fallback |
| Baseline (eval) | Direkt databashämtning / rådata | **Lucene** på `Chunk.content` (export `mode: baseline`) |
| UI | Illustration, ej operativt | **Operativ** workbench (direkt Neo4j + LLM i webbläsaren) |
| Ground truth | Manuell dubbelgranskning | **`ground_truth`** från dataset via `build_gold_set.py` |
| Resultat kap. 7 | Narrativ med siffror | PDF har **`[X]`** — narrativ före data är **fel** |

---

## Kapitel 1 — Inledning

### [FEL-1.1] Domän och exempel

**Nuvarande (missvisande):** Bonnier-specifika exempel (artiklar, journalister, ämnen) utan att säga att implementationen kör på HERB.

**Ersättning — lägg till efter problemformuleringen (ca 1.2):**

> I den genomförda implementationen används benchmarkkorpusen **HERB** (Salesforce), som innehåller strukturerad företagsinformation: produktdokument, Slack-trådar, pull requests, mötestranskript och fråge-svar-par. Studien är därmed metodiskt inriktad på **heterogen strukturerad JSON** och en **grafrepresentation i Neo4j**, medan samarbetet med Bonnier News motiverar krav på spårbarhet och kontrollerad informationshämtning i en redaktionell kontext. Exempel i senare kapitel som rör produkter, medarbetar-ID (`eid_…`) och kanaler ska läsas mot HERB, inte mot en specifik Bonnier-datamodell.

### [MISSVISANDE-1.2] “Generell metod oberoende av struktur”

**Ersättning — nyansera (ca 1.1 eller 3):**

> Pipeline-koden stödjer flera filformat (JSON, JSONL, Parquet m.fl.) via ett gemensamt chunking-lager, men **utvärdering och fullständig taggning** i denna studie är avgränsad till datasetet **`Salesforce__HERB`**. Generaliserbarhet diskuteras som designprincip, inte som empiriskt test över flera källor.

---

## Kapitel 2 — Syfte och forskningsfrågor

### [FEL-2.1] Baseline i syfte/RQ2

**Nuvarande:** “direkt databashämtning utan grafbaserad relationshantering”.

**Ersättning — 2. Syfte (sista stycket):**

> Utvärderingen genomförs som en kontrollerad jämförelse mellan (i) en **grafberikad hämtningsväg**, där frågan tolkas, taggar grundas mot en tagg-vokabulär i Neo4j och segment väljs via viktade `HAS_TAG`-relationer under en strukturell gate, och (ii) en **konventionell textbaseline**, där hämtning sker genom fulltextsökning (Lucene) över segmentens råtext **utan** tagg- eller gate-lager. Båda armarna serialiserar hämtade segment till samma typ av kontextpaket inför samma svarsmodell.

**Ersättning — RQ2 fotnot eller parentes:**

> Med “direkt hämtning” avses här **inte** SQL-frågor mot käll-Databaser utan den jämförande baseline som definieras i avsnitt 5.4 och 6.5 (fulltext på chunk-innehåll).

### [MISSVISANDE-2.2] Multi-hop

**Ersättning — under 2.1 eller 5.2:**

> Studien formulerar frågor som kan kräva information från flera segment eller produkter, men **implementerad retrieval utför inte explicit graftraversal över flera hopp** (t.ex. Cypher-kedjor). Relationell komplexitet hanteras indirekt genom taggmatchning, facet-vikter och eventuell lexikal fallback. Multi-hop diskuteras därför som **frågetyp**, inte som garanterad algoritmisk egenskap.

---

## Kapitel 5 — Metod

### [FEL-5.1] 5.2 Datamaterial

**Ersättning:**

> Datamaterialet utgörs av korpusen **HERB** (`Salesforce__HERB`), laddad till ett lokalt korpusarkiv och materialiserad i grafdatabasen **Neo4j** (databas `herb`). Varje payload-fil (produkt-JSON under `products/`, metadata under `metadata/`) upsertas som `:File`-noder och delas deterministiskt i `:Chunk`-segment med `locator_json` och fulltext i `content`. Den färdiga semantiska körningen identifieras med `run_id = pilot_full_herb` (5843 segment i full körning enligt projektdokumentation). För utvärdering används en härledd databas **`herb-eval`** där fråge-/oracle-ytor (`answerable_questions`, `unanswerable_questions`, `product_profile`) exkluderas för att minska läckage.

### [FEL-5.2] 5.3 Grafbaserad retrieval = traversal

**Ersättning — punktlista “Grafbaserad retrieval”:**

> - **Frågetolkning:** tvåpass LLM-produktion av frågebeskrivning, taggar och strukturell gate (`product`, `section`, `channel`, `employee_id`, `years`).
> - **Tagggrundning:** frågetaggar embeddas (samma modell som vid indexering) och matchas via **vektor-närmaste grannar** mot `:Tag.emb_<facet>` i Neo4j.
> - **Segmentranking:** viktad poängsättning längs `(:Chunk)-[:HAS_TAG {facet, w_chunk, w_facet, run_id}]->(:Tag)` kombinerat med `relevance_to_file` och gate-filter.
> - **Fallback:** om taggpoäng saknas under gate kan **fulltext** (`chunk_fulltext`) användas med varning i logg.

### [FEL-5.3] 5.4 Baseline

**Ersätt hela 5.4 med:**

> **5.4 Etablering av baseline**
>
> För att möjliggöra jämförelse etableras en **textuell baseline** som avsiktligt **inte** använder tagggraf, frågetolkning eller strukturell gate. I den implementerade utvärderingskedjan (`ragas-export`) motsvarar baseline:
>
> - **Input:** användarfrågan som ren text.
> - **Retrieval:** Neo4j fulltext-index **`chunk_content_ft`** över `Chunk.content` (Lucene), med samma dataset-scope och samma sektions-exkluderingar som graph-armen (`answerable_questions`, `unanswerable_questions`, `product_profile` på `herb-eval`).
> - **Begränsning:** vid export används standard tak **150 segment** när ingen explicit limit anges, eftersom ocappad Lucene-sökning kan returnera tusentals träffar och överbelasta svar-API:et.
> - **Svar:** samma svarsmodell, promptläge och temperatur som graph-armen.
>
> En alternativ baseline i workbench (**relevance baseline**) rangordnar segment efter fältet `relevance_to_file` (producerat i taggningssteget `score`) under samma gate som graph-armen; den används för interaktiv A/B-jämförelse men **inte** som primär arm i gold-100-exporten om inte annat anges.
>
> Som komplement finns en **SQL-agent-baseline** (SQLite över rå HERB-JSON, LLM med SQL-verktyg) som är **oberoende av Neo4j-grafen**; den redovisas separat om den inkluderas i slutlig eval.

### [FEL-5.4] 5.5 Två scenarier

**Ersättning:**

> **Scenario A (grafberikad):** fråga → tolkning → tagggrundning → viktad tagg-retrieval → serialiserat kontextpaket → LLM-svar.
>
> **Scenario B (textbaseline):** fråga → Lucene på rå segmenttext → serialiserat kontextpaket → LLM-svar (samma svarsteg).
>
> **Inte jämfört:** rå JSON-filer eller SQL direkt till LLM utan chunking (såvida inte SQL-agent-baseline används uttryckligen).

### [FEL-5.5] 5.7 Ground truth

**Ersättning:**

> Ground truth för gold-frågor hämtas från **datasetets egna answerable_questions**: fältet `ground_truth` i HERB:s `qa_record`-segment, extraherat med skriptet `python -m evaluation.build_gold_set` (read-only mot Neo4j). Detta är **auktoritativ dataset-etikett**, inte manuellt skriven av författarna från grunden.
>
> [VALFRITT OM NI GJORT MANUELL GRANSKNING UTANFÖR REPO — annars utelämna:]
> Ett urval av [N_VERIFY] frågor granskades manuellt för uppenbara feltolkningar innan export.
>
> **Ta bort** påståendet om obligatorisk dubbelgranskning av annan bedömare om det inte dokumenterats.

### [FEL-5.6] Operationalisering — hallucination

**Tillägg (5.6):**

> I den empiriska utvärderingen operationaliseras hallucination i första hand via **RAGAS faithfulness** (är svaret grundat i `retrieved_contexts`?) och kompletterande **context recall/precision** mot `reference`. De fyra manuella kategorierna i avsnitt 4.2 kan användas i kvalitativ felanalys men **mäts inte automatiskt** i nuvarande pipeline om inte separat kodats.

---

## Kapitel 6 — Systemdesign

### [FEL-6.1] 6.2 Artefaktens avgränsning — vektorer

**STREJK/RADERA:**

> “Vektorrepresentationer, vektorindex och bildbaserad indexering ligger utanför artefaktens omfattning.”

**Ersätt med:**

> **Inkluderat i artefakten:** efter semantisk extraktion (`extract`) körs steget **`embed-tags`**, som beräknar 384-dimensionella vektorer (`intfloat/e5-small-v2`) per tagg och facet (`emb_topic` … `emb_evidence`, samt `emb_all`) och skapar Neo4j-vektorindex `tag_emb_<facet>`. I frågetillfället embeddas prompt-taggar med samma modell och matchas mot dessa index (**tagggrundning**). Utan detta steg kan den grafbaserade hämtningsvägen inte köras (systemet felar högljutt).
>
> **Utanför scope:** bild-OCR, separat chunk-vektorindex över hela segment (endast tagg-vokabulär indexeras vektoriellt), produktionsdrift och extern API-hosting.

### [FEL-6.2] 6.2 UI

**STREIK/RADERA:**

> “Gränssnittet fungerar i nuvarande form som en arbetsyta för att illustrera pipeline- och urvalskoncepten” [utan operativ koppling].

**Ersätt med:**

> Workbench (Vite/React) är en **lokal forskningsprototyp** med **operativ** koppling till Neo4j (`neo4j-driver`) och LLM-leverantörer via webbläsaren. Usage-lane och Run Builder kör samma tjänstelogik som headless-exporten (`interpret` → `ground` → `scoreGroundedChunks` → `generateAnswer`). Pipeline-lane är **illustrativ** (offline Python-steg) och körs inte från UI.

### [FEL-6.3] 6.3.2 Semantisk berikning — “samma anrop”

**Ersätt hela stycket “Semantisk berikning” med:**

> **Semantisk berikning (offline, Anthropic).** Steget `extract` körs per segment i **två modellanrop**:
>
> 1. **Pass 1:** segmentbeskrivning (1–3 meningar) och lista av taggsträngar (inga facet-vikter).
> 2. **Pass 2:** för varje rensad tagg, facet-poäng i fem dimensioner (`topic`, `entities`, `activity`, `temporal`, `evidence`).
>
> Kantvikt **`w_chunk`** beräknas **deterministiskt i kod** från facet-vektorn (styrka × täckningsbonus); modellen emitterar inte `w_chunk`. För varje tagg skrivs en eller flera `HAS_TAG`-kanter (primär facet + extra vid facet ≥ 0,50).
>
> Därefter, per fil: **`describe`** (filsummering från segmentbeskrivningar) och **`score`** (jämförande `relevance_to_file` per segment inom filen, ett batched-anrop per fil).
>
> Modellutdata valideras med **tvingad tool/schema** (Anthropic) och Pydantic; fel loggas i `errors.jsonl` utan att tysta fortsätta.

### [FEL-6.4] 6.3.2 Filnivå — TAGGED rollup

**STREIK/RADERA:**

> “Aggregerade taggrelationer på filnivå härleds därefter genom en deterministisk operation direkt i grafen.” [om det avser `TAGGED`-kanter]

**Ersätt med:**

> Filnivå består av **`File.description`** (LLM) och segmentnivå av **`Chunk.relevance_to_file`** (LLM, jämförande inom fil). HERB-piloten skapar **inte** den äldre kanttypen `(:File)-[:TAGGED]->(:Tag)` (global fil-rollup); retrieval läser **`HAS_TAG`** direkt.

### [FEL-6.5] 6.4 Fem kluster → facet

**Global sök-ersätt i kap. 6:**

| Gammalt | Nytt (korrekt i kod) |
|---------|----------------------|
| kluster (på relation) | **facet** (på `HAS_TAG`) |
| fem kluster | fem **facetter** |
| `cluster` | använd inte för HERB |

### [FEL-6.6] 6.4 “Tomma segment”

**Nyansera:**

> I legacy-indexeringsvägen kan segment markeras `empty` med `empty_reason`. HERB-taggningspipelinen använder i stället **relevance_to_file** och urval vid analystillfälle; irrelevant material filtreras via gate, trösklar och limit — inte genom att radera segment ur grafen.

### [FEL-6.7] 6.5 Jämförelse baseline vs transformerat

**Ersätt punkt 1–2:**

> 1. **Textbaseline (eval):** Lucene på `Chunk.content` utan taggar/gate/tolkning (se 5.4).
> 2. **Grafberikad:** tagggrundning + viktad `HAS_TAG`-retrieval + gate + samma serialisering till LLM.

---

## Kapitel 7 — Resultat (mall med platshållare)

**VIKTIGT:** Ta bort all narrativ som påstår utfall **innan** platshållarna ersatts (t.ex. “det transformerade scenariot presterade bättre” med tomma tabeller).

### 7.1 Översikt

**Ersättning:**

> Utvärderingen genomfördes enligt avsnitt 5.5 på gold-mängden med `[N_GOLD]` frågor från HERB (`ragas-questions.herb-gold100.jsonl`), på grafdatabasen **`herb-eval`**. **Primär körning (tabell 7):** matchad top-**k**-retrieval (**k=40**) med ändlig tagggrundning (**grounding_k=20**, minSim=0,78) på båda armarna. Graph-armen (`A_tags_k40`) använder fullständig tolkning, e5-tagggrundning och viktad `HAS_TAG`-retrieval. Baseline-armen (`B_baseline_k40`) använder Lucene på rå `content` med samma **k=40**. **k** valdes före körning som fast evidensbudget (~40×1800 tecken per fråga), under pilotens ocappade retrieval (~120 segment/fråga i mediant), så att context precision rapporteras som **@40**. Svarsmodell: **[MODELL_SVAR]** (t.ex. deepseek-chat). RAGAS-domare: **[MODELL_JUDGE]**, samma tak **k=40** för judge som för svar-API. Temperatur: 0. Scorer deduplicerar per `id` om JSONL innehåller resume-rader.
>
> **Svarsgenerering (före RAGAS):** graph `[N_GRAPH_OK]/[N_GOLD]`, baseline `[N_BASE_OK]/[N_GOLD]`. Permanent exkluderade / fel: se `[PILOT_NOTE]`.

**[PILOT_NOTE] — kan klistras in tills slutlig:**

> **Pilot (stress, appendix):** ocappad export (`limit=0`, `grounding_k=0`, svar/judge @200) gav median ~120 graph-segment, ~13k taggträffar i grounding och RAGAS context precision ~0,04–0,06 @200. **Primär körning:** k=40 enligt ovan. Pilot visade API-fel (JSON body) vid stora kontextmängder, särskilt Slack-text. En fråga (`gold_personalizeforce_34`) failar permanent p.g.a. ogiltig hard gate (employee_id saknas i eval-korpus). RAGAS-judge kan timea ut vid parallell körning — se `--timeout 600`.

### 7.2 Svarskorrekthet

**Tabellmall:**

| Mått | Baseline | Graph (tagg) | Kommentar |
|------|----------|--------------|-----------|
| Andel besvarade (export) | `[N_BASE_OK]/[N_GOLD]` | `[N_GRAPH_OK]/[N_GOLD]` | utan `meta.error` |
| RAGAS answer_correctness (median, IQR) | `[MEDIAN_AC_BASE] ([IQR_AC_BASE])` | `[MEDIAN_AC_GRAPH] ([IQR_AC_GRAPH])` | kräver reference |
| RAGAS faithfulness (median, IQR) | `[MEDIAN_FA_BASE] ([IQR_FA_BASE])` | `[MEDIAN_FA_GRAPH] ([IQR_FA_GRAPH])` | |

> *[TEXT EFTER IFYLLNING: tolka skillnad; nämn partial answers om ni kodat det manuellt.]*

### 7.3 Retrieval och precision

| Mått | Baseline | Graph |
|------|----------|-------|
| context_recall (median, IQR) | `[MEDIAN_CR_BASE] ([IQR_CR_BASE])` | `[MEDIAN_CR_GRAPH] ([IQR_CR_GRAPH])` |
| context_precision (median, IQR) | `[MEDIAN_CP_BASE] ([IQR_CP_BASE])` | `[MEDIAN_CP_GRAPH] ([IQR_CP_GRAPH])` |
| Median antal retrieved contexts | `[MEDIAN_CTX_BASE]` | `[MEDIAN_CTX_GRAPH]` |

### 7.4 Hallucinationsfrekvens

> Primär operationalisering: **RAGAS faithfulness** (se tabell 7.3). De fyra kategorierna i avsnitt 4.2 analyseras endast i **[N_MANUAL_SAMPLE]** manuellt granskade svar om tid finns.

| Kategori (manuell, valfritt) | Baseline | Graph |
|------------------------------|----------|-------|
| Fabricerade entiteter | `[MAN_E1_BASE]` | `[MAN_E1_GRAPH]` |
| Felaktiga relationer | `[MAN_E2_BASE]` | `[MAN_E2_GRAPH]` |
| … | … | … |

### 7.5 Effektivitet och spårbarhet

| Mått | Baseline | Graph |
|------|----------|-------|
| Median tokens in (svar-API) | `[MEDIAN_TOK_BASE]` | `[MEDIAN_TOK_GRAPH]` |
| Median export-tid per fråga (ms) | `[MEDIAN_MS_BASE]` | `[MEDIAN_MS_GRAPH]` |

> Spårbarhet: graph-armen loggar `chunk_ids`, `file_ids`, gate och grounding i export-`meta`; baseline loggar primärt chunk-träffar utan tagg-härledning.

### 7.6 Sammanfattning (mall — fyll i först sedan skriv)

> Sammanfattningsvis visar den preliminära utvärderingen på `[N_GOLD]` frågor att **[SAMMANFATTNING_EFTER_SIFFROR]**. Resultaten är begränsade av exportkohort ([N_GRAPH_OK] resp. `[N_BASE_OK]` fullständiga svar) och bör tolkas tillsammans med felanalys i `[PILOT_NOTE]`. Statistisk generalisering utöver HERB/eval-grafen görs inte.

---

## Kapitel 8 — Diskussion (mall)

**Ersätt spekulativ text med:**

### 8.2 RQ1

> RQ1 besvaras genom att transformationslagret separerar (1) deterministisk segmentering och materialisering av strukturfält, (2) offline semantisk berikning (tvåpass taggning, fil-/segmentrelevans), (3) tagg-vektorindex för lexikal→grafisk grounding, och (4) analystids-urval som serialiserar segment — inte rå graf — till LLM. Detta är en **hybrid** graf- och vektor-RAG, inte ren multi-hop-traversal.

### 8.3 RQ2

> RQ2 besvaras empiriskt när `[MEDIAN_*]` är ifyllda. Tills dess: diskussionen begränsas till designhypoteser. **Möjlig tolkning om graph > baseline på context_recall:** taggar och gate minskar irrelevant kontext. **Möjlig tolkning om baseline ≥ graph på andel besvarade:** Lucene + lägre komplexitet undviker gate-fel och extremt stora kontextmängder. Båda kan vara sanna samtidigt.

### 8.6 Begränsningar

**Lägg till:**

> - En korpus (HERB), en eval-graf (`herb-eval`).
> - Retrieval är inte visad som optimal för alla frågetyper (person/company/url vs content).
> - Svar- och domarmodell ([MODELL_SVAR]) påverkar absolut nivå.
> - Export och RAGAS pågår; tabeller i kapitel 7 är utkast tills `[N_*]` ersatts.

---

## Kapitel 9 — Slutsats (mall)

> Studien har designat och implementerat ett transformationslager som materialiserar HERB i Neo4j, berikar segment med taggar och relevans, indexerar taggar vektoriellt och möjliggör fråge driven hämtning via tagggrundning och viktade `HAS_TAG`-kanter. Mot en **fulltextbaseline på rå segmenttext** utvärderades `[N_GOLD]` gold-frågor; slutsatser om överlägsenhet i svarskorrekthet, precision och hallucinationer **kräver ifyllda RAGAS-resultat** (kapitel 7). Det praktiska bidraget är en reproducerbar pipeline (preflight → tagging → materialize → embed-tags → workbench/export → RAGAS) och en tydlig skiljelinje mellan berikad graf-hämtning och okontrollerad text-sökning.

---

## Bilaga A — Kommandon (reproducibilitet i uppsatsen)

```bash
# Backend (herb)
cd backend
python scripts/bootstrap_schema.py
python scripts/run_preflight.py --dataset-id Salesforce__HERB
export PILOT_NAME=pilot_full_herb TAGGING_SELECTION_MODE=all
python -m tagging select && python -m tagging extract
python -m tagging describe && python -m tagging score
python -m tagging materialize && python -m tagging embed-tags

# Eval-graf
python scripts/create_herb_eval_db.py --replace
NEO4J_DATABASE=herb-eval python -m tagging embed-tags

# Gold + export
python -m evaluation.build_gold_set --count 100 --out ../frontend/scripts/ragas-questions.herb-gold100.jsonl
npm --workspace frontend run ragas:export -- --config ragas_exports/A_tags.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out ragas_exports/A_tags.jsonl
npm --workspace frontend run ragas:export -- --config ragas_exports/B_baseline.ragas.json \
  --questions frontend/scripts/ragas-questions.herb-gold100.jsonl --out ragas_exports/B_baseline.jsonl

# RAGAS (fyll platshållare från .report.json)
cd backend
python -m evaluation.ragas_eval --input ../ragas_exports/A_tags.jsonl \
  --metrics faithfulness,context_recall,context_precision \
  --report ../ragas_exports/A_tags.report.json --timeout 600
python -m evaluation.ragas_eval --input ../ragas_exports/B_baseline.jsonl \
  --metrics faithfulness,context_recall,context_precision \
  --report ../ragas_exports/B_baseline.report.json --timeout 600
```

---

## Bilaga B — Checklista före inlämning

- [ ] Alla “samma anrop” → tvåpass extract
- [ ] Inga “inga vektorindex” kvar
- [ ] Baseline definierad som Lucene (eval) + ev. fotnot om relevance-baseline i UI
- [ ] HERB nämnt som data, Bonnier som kontext
- [ ] Kap. 7: inga påståenden utan siffror; `[X]` ersatta eller tabeller borttagna
- [ ] `facet` inte `cluster` för HERB
- [ ] Ground truth: dataset + build_gold_set (ej påhittad dubbelgranskning)
- [ ] Figur/flöde: lägg till tagg-grounding (e5 → kNN → HAS_TAG)

---

## Bilaga C — Felkatalog (snabbreferens)

| ID | Allvar | Var i PDF | Kort beskrivning |
|----|--------|-----------|-----------------|
| FEL-6.2a | Hög | 6.2 | Vektorer utanför scope — **falskt** |
| FEL-6.2b | Hög | 6.2 | UI ej operativt — **falskt** |
| FEL-6.3 | Hög | 6.3.2 | Ett anrop beskrivning+taggar — **tvåpass** |
| FEL-5.4 | Hög | 5.4 | SQL/direkt DB-baseline — **Lucene** |
| FEL-5.3 | Medel | 5.3 | Traversal — **tagg-score** |
| FEL-5.7 | Medel | 5.7 | Manuell dubbelgranskning — **dataset GT** |
| FEL-7 | Hög | 7.x | Narrativ utan `[X]` ifyllda |
| FEL-1.1 | Medel | 1.x | Bonnier-exempel vs HERB-data |
| FEL-6.3b | Medel | 6.3.2 | TAGGED rollup — **ej HERB** |
| FEL-2.2 | Medel | 2.1 | Multi-hop som algoritm — **frågetyp** |

---

*Detta dokument är avsett att redigeras in i Word/PDF manuellt eller att kopieras avsnitt för avsnitt. Det ersätter inte handledargranskning.*
