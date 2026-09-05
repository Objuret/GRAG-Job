---
license: cc-by-nc-4.0
task_categories:
- text-retrieval
- question-answering
language:
- en
tags:
- enterprise-rag
- llm-agent
- evaluation
size_categories:
- 10K<n<100K
---
# Dataset Card for HERB

## Dataset Description
[HERB]() is a benchmark for evaluating LLM agents’ ability to perform **Deep Search** and **Long Context Reasoning**. It is generated using a synthetic data pipeline that simulates business workflows across product planning, development, and support stages, generating interconnected content with realistic noise and multi-hop questions with guaranteed ground-truth answers.

### Directory Structure

```
data/
├── metadata/
│   ├── customers_data.json
│   ├── salesforce_team.json
│   └── employee.json
└── products/
    ├── TrendForce.json
    ├── ContextForce.json
    ├── CollaborationForce.json
    └── ... (other product files)
```

### Contents

#### 1. `metadata/`

This folder contains supporting data about employees and customers involved in products.

- **customers_data.json**  
  Contains a list of customer profiles, each with fields such as `name`, `role`, `company`, and a unique `id` (e.g., `CUST-0001`).  

- **salesforce_team.json**  
  Describes the organizational structure of the Salesforce team, including VPs, engineering leads, engineers, and QA specialists. The structure is hierarchical, with each leader listing their direct reports and their roles.

- **employee.json**  
  A mapping of employee IDs to detailed employee profiles, including `employee_id`, `name`, `role`, `location`, and `org`. This file is used to resolve references in other files (such as team or product assignments).

#### 2. `products/`

This folder contains data for each product in SynthEKG/HERB. Each product has its own JSON file, named as `<ProductName>.json`.

> **RAG Evaluation Note:** For RAG evaluations, do not use the `team` and `customers` fields directly to answer questions. These fields are provided only for oracle/long-context evaluationsettings only. For RAG evaluations, these should be inferred from either other artifacts (e.g., Slack messages) or from `metadata/*`. 

Each product file typically contains:
- **team**: List of employee IDs (`eid_...`) who are part of the product team.
- **customers**: List of customer IDs (`CUST-...`) associated with the product.
- **artifacts**: Array of **Slack messages/ meeting transcripts/ meeting chats/ documents/ urls/ pull requests/ answerable questions/ unanswerable questions** related to the product.

Example structure from `TrendForce.json`:
```json
{
  "team": ["eid_792d7501", "eid_82e9fcef", ...],
  "customers": ["CUST-0010", "CUST-0075", ...],
  "slack": [
    {
      "sender": "eid_36319f22",
      "message": "Hi team, I just wanted to kick off our discussion...",
      "timestamp": "2026-03-12T08:24:00",
      "id": "20260312-0-df79b"
    },
    ...
  ],
  .....
}
```

## Paper Information

- Paper: https://arxiv.org/abs/2506.23139
- Code: https://github.com/SalesforceAIResearch/HERB


## Citation
```bibtex
@article{choubey2025benchmarkingdeepsearchheterogeneous,
      title={Benchmarking Deep Search over Heterogeneous Enterprise Data}, 
      author={Prafulla Kumar Choubey and Xiangyu Peng and Shilpa Bhagavath and Kung-Hsiang Huang and Caiming Xiong and Chien-Sheng Wu},
      year={2025},
      eprint={2506.23139},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2506.23139}, 
}
```

## Ethical Considerations
This dataset was generated using GPT-4o and should not be used to develop models that compete with OpenAI.

This release is for research purposes only in support of an academic paper. Our models, datasets, and code are not specifically designed or evaluated for all downstream purposes. We strongly recommend users evaluate and address potential concerns related to accuracy, safety, and fairness before deploying this model. We encourage users to consider the common limitations of AI, comply with applicable laws, and leverage best practices when selecting use cases, particularly for high-risk scenarios where errors or misuse could significantly impact people's lives, rights, or safety. For further guidance on use cases, refer to our AUP and AI AUP.