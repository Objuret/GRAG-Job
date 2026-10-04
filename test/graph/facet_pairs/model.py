"""PairRanker: ONE encoder pass per (tag, chunk) edge, five facet scores out.

The encoder and the pooling are the 2026-09-17 cross-encoder's
(`test/graph/facet_neural/model.py`): backbone `tasksource/deberta-small-long-nli`, the pair
`[CLS] tag [SEP] chunk [SEP]` with `truncation="only_second"` so the tag side is never cut, and
the pooled representation is the first token concatenated with the attention-masked mean. The
pooled vector goes through ONE shared projection and is then read by five scalar heads
(topic, temporal, why, activity, concreteness) that share no parameters among themselves —
exactly the 09-17 FacetModel's shape, with five heads where it had four.

What changed on 2026-09-18, and why. The first build put the facet word into the input text
(`<facet>: <tag>`) and added a learned facet embedding, so an edge needed FIVE encoder passes,
one per facet. That was measured on the 1080 Ti at 0.89 edges/s, which is about 19 h for one
pass over the 61,018 edges. With the facet moved out of the text and into the heads, an edge is
ONE forward pass and the five numbers fall out of it together. The expectation is therefore
about a 5x speed-up, roughly 4.5 edges/s and about 4 h a pass — an expectation stated here to
be MEASURED by `score_all.py`, which prints edges/s, and never to be quoted as a measurement.

The facet word is deliberately absent from the text: the judge's facet definitions live in the
judge's prompt, and a bare facet name in a DeBERTa input is a token, not a definition. What
separates the five is the five heads and the comparisons they are fitted to.

Davidson's tie parameter (one per facet, learned) is carried here as a parameter so it travels
in the artifact with the weights that produced it.

The artifact is a directory, as in the 09-17 build: `model.safetensors`, the tokenizer's files,
`pair_config.json`, `backbone_config.json`. `PairRanker.load` rebuilds from it alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn

# The five facets, in the order every column, array and score row uses. topic is first because
# it is the one the numeric mapping is later read off (`map_topic.py`) — its known values are
# never seen during training.
FACETS = ("topic", "temporal", "why", "activity", "concreteness")

FACET_INDEX = {f: i for i, f in enumerate(FACETS)}

BACKBONE = "tasksource/deberta-small-long-nli"

# Carried over unchanged from the 09-17 build so the two instruments are comparable.
PROJ_DIM = 256
HEAD_DIM = 64
DROPOUT = 0.10


def pair_first_segment(tag: str) -> str:
    """The first segment of the pair: the tag alone. Never truncated, never decorated."""
    return str(tag)


class PairRanker(nn.Module):
    def __init__(self, backbone: str = BACKBONE, revision: str | None = None,
                 proj_dim: int = PROJ_DIM, head_dim: int = HEAD_DIM,
                 dropout: float = DROPOUT, encoder=None):
        super().__init__()
        from transformers import AutoConfig, AutoModel

        if encoder is not None:
            self.encoder = encoder
            self.config = encoder.config
        else:
            self.config = AutoConfig.from_pretrained(backbone, revision=revision)
            self.encoder = AutoModel.from_pretrained(backbone, revision=revision,
                                                     config=self.config)
        d = int(self.config.hidden_size)
        self.backbone_name = backbone
        self.backbone_revision = revision
        self.proj_dim = int(proj_dim)
        self.head_dim = int(head_dim)
        self.dropout_p = float(dropout)
        self.pooled_dim = 2 * d

        self.projection = nn.Sequential(
            nn.Linear(self.pooled_dim, self.proj_dim),
            nn.GELU(),
            nn.LayerNorm(self.proj_dim),
            nn.Dropout(self.dropout_p),
        )
        self.heads = nn.ModuleDict({
            f: nn.Sequential(
                nn.Linear(self.proj_dim, self.head_dim),
                nn.GELU(),
                nn.Dropout(self.dropout_p),
                nn.Linear(self.head_dim, 1),
            ) for f in FACETS
        })

        # Davidson's tie parameter nu, per facet, held as log nu so it stays positive under an
        # unconstrained optimiser. log nu = 0 (nu = 1) is the starting default: at equal scores
        # it makes a tie exactly as likely as either win (1/3 each), the neutral start before
        # any facet's real tie rate is seen.
        self.tie_log = nn.Parameter(torch.zeros(len(FACETS)))

    # ------------------------------------------------------------------ forward

    def pair_representation(self, input_ids, attention_mask, **kw):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask, **kw)
        h = out.last_hidden_state                                   # B x L x D
        cls = h[:, 0]
        mask = attention_mask.unsqueeze(-1).to(h.dtype)
        mean = (h * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
        return torch.cat([cls, mean], dim=-1)                       # B x 2D

    def forward(self, input_ids, attention_mask, **kw):
        """B x 5: every facet's score for every row, from ONE encoder pass."""
        shared = self.projection(self.pair_representation(input_ids, attention_mask, **kw))
        return torch.cat([self.heads[f](shared) for f in FACETS], dim=-1)

    def score_facets(self, input_ids, attention_mask, facet_ids, **kw):
        """B: each row's score on the facet its `facet_ids` entry names."""
        all_scores = self.forward(input_ids, attention_mask, **kw)
        return all_scores.gather(-1, facet_ids.unsqueeze(-1)).squeeze(-1)

    def nu(self, facet_ids):
        """Davidson's tie parameter for each row's facet."""
        return self.tie_log[facet_ids].exp()

    # ------------------------------------------------------------------ freezing

    def set_stage(self, stage: str) -> dict:
        """A = the whole backbone frozen, B = its last two transformer layers unfrozen.
        The same two-stage schedule as the 09-17 build, and it returns the same record."""
        if stage not in ("A", "B"):
            raise ValueError(f"stage must be 'A' or 'B', got {stage!r}")
        for p in self.encoder.parameters():
            p.requires_grad = False
        unfrozen = []
        if stage == "B":
            layers = self.encoder.encoder.layer
            for i in (len(layers) - 2, len(layers) - 1):
                for name, p in layers[i].named_parameters():
                    p.requires_grad = True
                    unfrozen.append(f"encoder.encoder.layer.{i}.{name}")
        for p in self.projection.parameters():
            p.requires_grad = True
        for p in self.heads.parameters():
            p.requires_grad = True
        self.tie_log.requires_grad = True
        return {
            "stage": stage,
            "n_encoder_layers": len(self.encoder.encoder.layer),
            "unfrozen_encoder_parameters": unfrozen,
            "trainable_parameters": sum(p.numel() for p in self.parameters()
                                        if p.requires_grad),
            "frozen_parameters": sum(p.numel() for p in self.parameters()
                                     if not p.requires_grad),
        }

    def head_parameters(self):
        return (list(self.projection.parameters()) + list(self.heads.parameters())
                + [self.tie_log])

    def encoder_parameters(self):
        return [p for p in self.encoder.parameters() if p.requires_grad]

    # ------------------------------------------------------------------ artifact

    def save(self, path, tokenizer=None, extra: dict | None = None) -> Path:
        from safetensors.torch import save_file

        out = Path(path)
        out.mkdir(parents=True, exist_ok=True)
        state = {k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}
        save_file(state, str(out / "model.safetensors"))
        cfg = {
            "architecture": "PairRanker",
            "facets": list(FACETS),
            "backbone": self.backbone_name,
            "backbone_revision": self.backbone_revision,
            "hidden_size": int(self.config.hidden_size),
            "num_hidden_layers": int(self.config.num_hidden_layers),
            "pooling": "concat(first_token, attention_masked_mean)",
            "encoder_passes_per_edge": 1,
            "facet_conditioning": "five scalar heads over one shared projection; the facet is "
                                  "NOT in the input text",
            "projection": f"Linear({self.pooled_dim}->{self.proj_dim}) GELU LayerNorm "
                          f"Dropout({self.dropout_p})",
            "head": f"Linear({self.proj_dim}->{self.head_dim}) GELU "
                    f"Dropout({self.dropout_p}) Linear({self.head_dim}->1), one per facet",
            "proj_dim": self.proj_dim,
            "head_dim": self.head_dim,
            "dropout": self.dropout_p,
            "output_activation": "identity (a latent strength, not a calibrated amount)",
            "tie_model": "Davidson (1970) Bradley-Terry with ties, nu per facet, learned",
            "tie_log": [float(v) for v in self.tie_log.detach().cpu()],
            "pair_format": "[CLS] <tag> [SEP] chunk [SEP], truncation=only_second",
            "known_topic_values_in_training": False,
        }
        cfg.update(extra or {})
        (out / "pair_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        (out / "backbone_config.json").write_text(self.config.to_json_string(),
                                                  encoding="utf-8")
        if tokenizer is not None:
            tokenizer.save_pretrained(str(out))
        return out

    @classmethod
    def load(cls, path, device: str = "cpu"):
        """Rebuild from the artifact alone: architecture from the stored backbone config,
        every weight from `model.safetensors`. No download of trained weights."""
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoModel

        d = Path(path)
        cfg = json.loads((d / "pair_config.json").read_text(encoding="utf-8"))
        bb = AutoConfig.from_pretrained(str(d / "backbone_config.json"))
        encoder = AutoModel.from_config(bb)
        model = cls(backbone=cfg["backbone"], revision=cfg.get("backbone_revision"),
                    proj_dim=cfg["proj_dim"], head_dim=cfg["head_dim"],
                    dropout=cfg["dropout"], encoder=encoder)
        missing, unexpected = model.load_state_dict(
            load_file(str(d / "model.safetensors")), strict=False)
        if missing or unexpected:
            raise RuntimeError(f"pair ranker artifact mismatch: missing {missing[:5]}, "
                               f"unexpected {unexpected[:5]}")
        model.to(device).eval()
        return model, cfg


def load_tokenizer(path_or_name: str, revision: str | None = None):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(path_or_name), revision=revision)


def encode_rows(tokenizer, tags: list, chunks: list, max_length: int):
    """Encode (tag, chunk) rows. The tag side is never truncated. No facet enters the text."""
    first = [pair_first_segment(t) for t in tags]
    return tokenizer(first, chunks, truncation="only_second", max_length=max_length,
                     padding=True, return_tensors="pt")


def facet_id_tensor(facets: list, device=None):
    return torch.tensor([FACET_INDEX[f] for f in facets], dtype=torch.long, device=device)
