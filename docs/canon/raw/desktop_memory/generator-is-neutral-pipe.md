---
name: generator-is-neutral-pipe
description: "The shared generator is a thin RAG pipe — one fixed generic grounding system prompt (answer only from the docs, be concise), identical across arms; NO abstention/behavioural steering; structured {answer}; arms own advanced handling"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1c4535a5-51e6-43f6-9cc9-fff00aa972b6
---

The v3 shared generator (`orchestrator.build_shared_generator`) sends the model one
fixed system instruction — *"Answer the question using only the provided documents. Be
concise."* — then the question exactly as posed in the dataset plus the arm's retrieved
passages as a labelled user turn. Output is a structured `{answer}` (a format constraint
only, never content). `temperature=0` and thinking disabled for reproducibility.

The instruction is **generic grounding, not retrieval engineering**, and is held
byte-identical across all three arms, so the only variable stays the retrieval.

**The line:** generic RAG grounding (use the docs, be concise) is allowed; **behavioural
steering that manufactures scoring artifacts is not** — specifically NO forced
abstention / "I don't know" string. A forced abstention instruction made the model emit
"I don't know" (~61% on a gold-100 vector run); an audit of those 55 abstentions found 0
over-abstentions — every one was a genuine retrieval miss — but the clean refusal token
was an artifact of the prompt, not native behaviour, and it masks what we measure.

**How to apply:** keep the generator a thin pipe with only that generic grounding. If an
arm wants smarter handling of thin/empty context (abstention, reranking-aware prompting,
etc.) that lives inside THAT arm's own code, never in the shared generator. See
[[arms-share-only-corpus-and-generator]] and [[v3-arm-model-stack]].
