"""Dataset source registry for raw dataset layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HFDatasetSource:
    name: str
    repo_id: str
    target: str


@dataclass(frozen=True)
class ExternalFileSource:
    dataset: str
    url: str
    target: str


HF_DATASETS: list[HFDatasetSource] = [
    HFDatasetSource(
        name="Salesforce/HERB",
        repo_id="Salesforce/HERB",
        target="raw/Salesforce__HERB",
    ),
    HFDatasetSource(
        name="VLR-CVC/DocVQA-2026",
        repo_id="VLR-CVC/DocVQA-2026",
        target="raw/VLR-CVC__DocVQA-2026",
    ),
    HFDatasetSource(
        name="wenhu/hybrid_qa",
        repo_id="wenhu/hybrid_qa",
        target="raw/wenhu__hybrid_qa/hf_repo",
    ),
    HFDatasetSource(
        name="fever/feverous",
        repo_id="fever/feverous",
        target="raw/fever__feverous/hf_repo",
    ),
]


EXTERNAL_FILES: list[ExternalFileSource] = [
    ExternalFileSource(
        dataset="wenhu/hybrid_qa",
        url="https://raw.githubusercontent.com/wenhuchen/HybridQA/master/released_data/train.json",
        target="raw/wenhu__hybrid_qa/released_data/train.json",
    ),
    ExternalFileSource(
        dataset="wenhu/hybrid_qa",
        url="https://raw.githubusercontent.com/wenhuchen/HybridQA/master/released_data/dev.json",
        target="raw/wenhu__hybrid_qa/released_data/dev.json",
    ),
    ExternalFileSource(
        dataset="wenhu/hybrid_qa",
        url="https://raw.githubusercontent.com/wenhuchen/HybridQA/master/released_data/test.json",
        target="raw/wenhu__hybrid_qa/released_data/test.json",
    ),
    ExternalFileSource(
        dataset="fever/feverous",
        url="https://fever.ai/download/feverous/feverous_train_challenges.jsonl",
        target="raw/fever__feverous/data/feverous_train_challenges.jsonl",
    ),
    ExternalFileSource(
        dataset="fever/feverous",
        url="https://fever.ai/download/feverous/feverous_dev_challenges.jsonl",
        target="raw/fever__feverous/data/feverous_dev_challenges.jsonl",
    ),
    ExternalFileSource(
        dataset="fever/feverous",
        url="https://fever.ai/download/feverous/feverous_test_unlabeled.jsonl",
        target="raw/fever__feverous/data/feverous_test_unlabeled.jsonl",
    ),
]


