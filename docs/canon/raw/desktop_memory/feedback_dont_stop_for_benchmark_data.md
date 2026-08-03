---
name: feedback-dont-stop-for-benchmark-data
description: "Don't pause git/push workflows to flag benchmark datasets as potentially sensitive company data"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9a4a791b-4724-4e7a-ac7c-456dcbebdea4
---

Don't stop a git commit/push workflow to ask whether benchmark or evaluation datasets look like "real company data." Both HERB (Salesforce) and Bonnier datasets in this repo are synthetic or public benchmark data created to look like enterprise data — that's the point of the dataset. Flagging them as sensitive before pushing is wrong and breaks the flow.

**Why:** User was frustrated when I halted a push to ask about Bonnier CSVs. They are evaluation/benchmark datasets, not actual client data with privacy concerns.

**How to apply:** When staging and pushing untracked files in this repo, include all data files in `backend/data/` subdirectories (except those already gitignored like `backend/data/raw/`) without pausing to ask about privacy. Proceed with the full commit.
