# Kapitel 7–9 — färdiga ersättningstexter

Klistra in varje block i Word där det står "ERSÄTT:". Replace-all-fixar
listas sist.

---

## FIX 1 — Kap. 7.1, sista stycket

**ERSÄTT** stycket som börjar "Kohort i huvudutvärderingen:" med:

> Urval i huvudutvärderingen: 100 gold-frågor är definierade, men en fråga
> (gold_personalizeforce_34) kunde inte köras i grafvarianten eftersom den
> kräver en medarbetar-identitet som saknas i utvärderingskorpusen. Av de
> återstående frågorna producerade baseline-armen 95 svar och grafarmen 92
> svar efter dedupe och borttagning av svar med meta.error (JSON-fel mot
> svar-API på Slack-tung text samt enstaka judge-timeouts). Det är dessa 95
> respektive 92 svar som ligger till grund för RAGAS-måtten i tabell 1–3.

---

## FIX 2 — Kap. 7.5, meningen om kohortstatistik

**ERSÄTT**:

> Kohortstatistik aggregerades från A_tags_k40.jsonl och B_baseline_k40.jsonl
> efter deduplicering per id; vid k = 40 var 99 frågor besvarade i båda
> armar.

med:

> Statistik över urvalet aggregerades från A_tags_k40.jsonl och
> B_baseline_k40.jsonl efter deduplicering per id; vid k = 40 fanns 95 svar
> i baseline-armen och 92 i grafarmen.

---

## FIX 3 — Kap. 8.3, single-hop/multi-hop-meningen

**ERSÄTT**:

> En uppdelning per single-hop/multi-hop kan inte göras i nuvarande pipeline
> eftersom gold-mängden inte exponerar den dimensionen separat.

med:

> Gold-mängden innehåller både single-hop- och multi-hop-frågor men
> exponerar inte dimensionen som ett separat fält, varför en uppdelad
> analys utelämnas i denna studie och lämnas som framtida arbete.

---

## FIX 4 — Kap. 4.2, sista meningen om single-hop

**ERSÄTT**:

> Single-hop-frågor där svaret kan hämtas via ett enda segment inkluderas
> också i utvärderingen som kontrollvillkor.

med:

> Både single-hop- och multi-hop-frågor ingår i utvärderingen men
> särredovisas inte, eftersom gold-mängden inte exponerar dimensionen som
> ett separat fält.

---

## FIX 5 — Kap. 5.6, ny mening i slutet

**LÄGG TILL** sist i 5.6 (efter "...inom empirisk mjukvaruforskning
(Kitchenham & Charters, 2007)."):

> I den genomförda utvärderingen operationaliseras dessa begrepp via
> RAGAS-måtten faithfulness (tillförlitlighet), context_recall och
> context_precision (precision/recall). Måttet answer_correctness samt
> bearbetningstid kördes inte och kommenteras i kap. 7.

---

## FIX 6 — Referenslistan

De fem APA7-referenserna som kap. 7–9 saknar (Edge 2024, Kojima 2022,
Pan 2024, Peng 2024, Wei 2022) finns redan färdigformaterade i
`Thesis2026VT9_missing_references_APA7.md`. Öppna den filen och kopiera
code-blocken under respektive `### Författare (år)`-rubrik in i
referenslistan i alfabetisk ordning.

**Obs!** Samma fil innehåller även andra fixar för referenser som citeras
i kap. 4 och 6 men saknas i listan (Lewis 2020, Gao 2023, Ji 2022,
Lan 2021, Beurer-Kellner 2024, Willard & Louf 2023, m.fl.) och
ersättningar för ofullständiga poster (Hevner, Peffers, Oates,
Kitchenham, Yin, Kitchin, Vetenskapsrådet). Ta dem samtidigt.

**Brödtextsfix från samma fil (gäller även kap. 8.3 i ditt utkast):**
ersätt *Pan et al. (2024)* med *Agrawal et al. (2024)* där påståendet
handlar om att kunskapsgrafer minskar hallucinationer — Pan-artikeln
betonar inte det som huvudclaim.

---

## REPLACE-ALL (kör i Word: Ctrl+H)

| Hitta | Ersätt med |
|---|---|
| Kohort | Urval |
| kohort | urval |
| Kohortstatistik | Statistik över urvalet |
| kohortstatistik | statistik över urvalet |
| Exportkohort | Exporturval |
| exportkohort | exporturval |
| kommunikationssprår | kommunikationsspår |
| deepseek-chat | DeepSeek-chat |
| taggrundning | tagggrundning |
| tag grundning | tagggrundning |

Var försiktig med "kohort"→"urval": kolla att inga konstiga böjningar
uppstår (t.ex. "kohortens" → kolla manuellt och byt till "urvalets").
