# Chunk Keyword Extractor

Answer each cluster with telegram-style retrieval keywords.

Cluster key = parent:
topic, entities, activity, temporal, evidence.

Keyword: short atomic snake_case name + relevance weight.
Include weak signals with low weight. Skip only clusters with no signal.
Do not copy raw IDs; summarize ID lists as *_id_list or *_identifier_list.
If meaningless: empty=true, empty_reason, all clusters=[].
Copy chunk_end_offset exactly.
