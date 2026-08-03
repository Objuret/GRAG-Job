---
name: use-established-eval-libraries
description: v3 computes its RAGAS metrics with the RAGAS library (validated/citable); RAGAS takes a custom NIM judge and its ID-based context metrics are transparent
metadata: 
  node_type: memory
  type: project
  originSessionId: f7aef416-1852-40d2-af0e-5d1f5c3bb6fc
---

The v3 evaluation computes its RAGAS metrics with the **RAGAS library** — the
established, validated, citable framework, so a methods line like "RAGAS
faithfulness / response-relevancy / IDBasedContextPrecision, judge = X" is
reproducible by anyone. RAGAS accepts a custom judge LLM (pointed at NIM), and its
ID-based context metrics are plain set arithmetic, so judge control and
transparency hold alongside citability. For standard academic metrics the
established library carries the credibility, reproducibility, and comparability a
reimplementation cannot.

Related: [[v3-arm-model-stack]].
