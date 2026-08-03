---
name: design-before-build
description: v2 build gate — every part must be explicitly decided/approved before writing pipeline code; building implies the design is closed
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 404340d3-17bf-43cf-9228-1997a109dc2c
---

Starting to build means asserting the design is closed. The user erupted when code appeared while design questions were still open ("that means we fucking have to make sure all parts are decided upon first").

**Why:** Code written against an undecided design bakes assistant assumptions into the artefact — the exact failure mode v2 exists to fix. Related: [[noncontamination-rework-unapproved]], [[no-cutting-corners]].

**How to apply:** Before any new pipeline stage is coded, present the decided-vs-open checklist for it and get explicit sign-off that its design is closed. "Get on with building" means close the remaining decisions first, not skip them.
