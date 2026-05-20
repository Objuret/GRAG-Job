# Kap 6 — Ersättningstext (kopiera till Word)

**Användning:** Ersätt motsvarande avsnitt i *Thesis2026VT.pdf*. Detta är en **komprimerad** version av `Thesis2026VT_korrigeringar.md` fokuserad på kapitel 6. Resultat (kap. 7) har platshållare i det andra dokumentet.

---

## 6.1 Designgrund och mål

Designen utgår från att LLM-baserad analys av heterogent material i hög grad beror på hur materialet representeras innan det når modellen. Artefakten är ett **transformationslager** som (1) bevarar råmaterial oförändrat i segmenttext, (2) skapar en enhetlig Neo4j-representation med spårbara locators och strukturfält, (3) berikar segment semantiskt offline, (4) indexerar taggar vektoriellt för frågetillfället, och (5) serialiserar ett **urval** av segment till ett kontextpaket — inte hela grafen — inför LLM-analys.

---

## 6.2 Artefaktens avgränsning

**Ingår:** inläsning och klassificering av råmaterial; deterministisk segmentering; HERB-taggningspilot (`python -m tagging`: extract, describe, score, materialize, embed-tags); lagring i Neo4j; lokal workbench med operativ fråge-/retrieval-körning; headless RAGAS-export.

**Ingår också (viktigt):** vektorindex på `:Tag` (`emb_topic` … `emb_evidence`, `emb_all`) och tagggrundning vid frågor med samma modell (e5-small-v2) som vid indexering.

**Ingår inte:** produktionsdrift, användarhantering, extern API-hosting; bild-OCR; separat vektorindex över hela segmenttext (endast tagg-vokabulär); legacy fil-rollup `(:File)-[:TAGGED]->(:Tag)`.

**Gräns mot analys:** Transformationslagret berikar och indexerar. Svar genereras i efterföljande steg (workbench/export) och är det som jämförs i utvärderingen.

---

## 6.3 Systemstruktur

### 6.3.1 Datainput

Systemet tar emot heterogent material (JSON, JSONL, Parquet, text). I studien är källan **HERB** (`Salesforce__HERB`): produkt-JSON och metadata. Varje fil registreras som `:File` med hash, sökväg och format; chunkbara filer blir `:Chunk` med `locator_json` och `content`. Filer utan textuella segment (t.ex. vissa bilder/arkiv) kan finnas som metadata men går inte vidare till semantisk berikning.

### 6.3.2 Transformationslager

**Steg 1 — Segmentering (deterministisk, ingen LLM).** Varje fil delas enligt format- och domänregler (för HERB: produktsektioner, Slack per kanal, dokumentdelar, QA-poster m.m.). Segment är reproducerbara och spårbara via `chunk_id`, `file_id`, ordinal och locator.

**Steg 2 — Semantisk berikning (offline, Anthropic).** Per segment körs `extract` i **två modellanrop**:

1. *Pass 1:* kort segmentbeskrivning och lista av taggsträngar (inga facet-vikter).
2. *Pass 2:* facet-poäng (0–1) per tagg i fem dimensioner: topic, entities, activity, temporal, evidence.

Vikt **`w_chunk`** beräknas i kod från facet-vektorn; modellen emitterar den inte. Kanter `(:Chunk)-[:HAS_TAG {facet, w_chunk, w_facet, run_id}]->(:Tag)` skrivs för primär facet och vid facet ≥ 0,50.

Per fil: **`describe`** (filsummering) och **`score`** (jämförande `relevance_to_file` per segment, ett batched-anrop per fil).

**Steg 3 — Materialisering och index (deterministiskt + lokalt embedding).** `materialize` lyfter strukturfält (product, section, channel, employee_id, years m.m.) till `:Chunk` för hård gate. `embed-tags` beräknar vektorer på `:Tag` och skapar vektorindex `tag_emb_<facet>`.

### 6.3.3 Output till språkmodell

Grafen är **index- och urvalslager**, inte promptformat. Vid analystillfälle: fråga → tolkning → tagggrundning (kNN) → viktad segmentranking → serialisering (segmenttext, beskrivningar, poäng, käll-ID). LLM får ett kontextpaket (strukturerad text), inte Cypher eller rå JSON-filer.

### 6.3.4 LLM-baserad analys

Analysen sker efter transformationslagret i workbench eller export-harness. Utvärdering jämför **grafberikad hämtning** mot **fulltextbaseline** (Lucene på `Chunk.content`) med samma svarsmodell och temperatur — se kapitel 5.4 och 7.

---

## 6.4 Designbeslut (korrigerade punkter)

**Modulär separation.** Backend (indexering/tagging) och frontend (tolkning/retrieval/svar) delar Neo4j-kontraktet men kan köras separat.

**Graf som mellanrepresentation.** Relationer uttrycks via `:Source`/`:File`/`:Chunk`/`:Tag` och `HAS_TAG`; urval och spårbarhet sker på denna modell.

**Deterministisk segmentering.** Segmentgränser sätts av regler, inte av LLM.

**Fem facetter.** Facett lagras på `HAS_TAG`-kanten (samma taggnamn kan ha olika facet i olika kontexter).

**Tvåpass extraktion, inte ett anrop.** Beskrivning och tagglista (pass 1) skiljs från facet-scoring (pass 2).

**Schemastyrda modellutdata.** Tvingad struktur vid tagging; validering innan grafskrivning.

**Relevansviktning.** `relevance_to_file` styr urval/ranking; segment raderas inte ur grafen.

**Taggvektorer ingår.** Tagggrundning är obligatorisk för den grafbaserade hämtningsvägen.

**Tydlig gräns mot analys.** All svarsgenerering sker efter urval/serialisering.

---

## 6.5 Koppling till utvärderingen

**Scenario A (grafberikad):** tolkning + tagggrundning + viktad `HAS_TAG`-retrieval under gate → kontextpaket → LLM.

**Scenario B (textbaseline):** Lucene på rå `Chunk.content` (utan taggar/gate) → kontextpaket → LLM.

Konstanta: gold-frågor, temperatur 0, samma svarsmodell. Variabel: hämtningsväg. Mått: RAGAS (faithfulness, context recall/precision) + andel besvarade exportrader — se kapitel 7 med platshållare tills export är klar.

---

*Slut kap 6 — ersättningstext*
