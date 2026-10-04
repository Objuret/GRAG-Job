"""The four-facet cross-encoder: one (tag, chunk) pair in, four signed facet values out.

Section 12 of the specification. The backbone is loaded from its checkpoint and its own
config supplies every architecture number; nothing here duplicates a hidden size or a layer
count by hand. The pair is `[CLS] tag [SEP] chunk [SEP]` with `truncation="only_second"`, so
the tag is never cut. The pooled representation is the first token concatenated with the
mask-aware mean, projected once, and then read by four heads that share no parameters.

Under Correction 1 there is no SCALE: the target is the signed relevance loss in the ruler's
own units and the output activation is the identity.

The artifact is a directory: `model.safetensors` (backbone, projection and all four heads in
one state dict), the tokenizer's own files, and `facet_config.json` with everything section 20
names. `FacetModel.load` rebuilds from that directory alone.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from torch import nn

FACETS = ("temporal", "why", "activity", "concreteness")

BACKBONE = "tasksource/deberta-small-long-nli"

PROJ_DIM = 256

HEAD_DIM = 64

DROPOUT = 0.10


class FacetModel(nn.Module):
    def __init__(self, backbone: str = BACKBONE, revision: str | None = None,
                 proj_dim: int = PROJ_DIM, head_dim: int = HEAD_DIM,
                 dropout: float = DROPOUT, config=None, encoder=None):
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
        self.proj_dim, self.head_dim, self.dropout_p = int(proj_dim), int(head_dim), float(dropout)
        self.projection = nn.Sequential(
            nn.Linear(2 * d, self.proj_dim),
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

    # ------------------------------------------------------------------ forward

    def pair_representation(self, input_ids, attention_mask, **kw):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask, **kw)
        h = out.last_hidden_state                                  # B x L x D
        cls = h[:, 0]
        mask = attention_mask.unsqueeze(-1).to(h.dtype)
        mean = (h * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
        return torch.cat([cls, mean], dim=-1)                      # B x 2D

    def forward(self, input_ids, attention_mask, **kw):
        shared = self.projection(self.pair_representation(input_ids, attention_mask, **kw))
        return torch.cat([self.heads[f](shared) for f in FACETS], dim=-1)   # B x 4

    # ------------------------------------------------------------------ freezing

    def set_stage(self, stage: str) -> dict:
        """Stage A freezes the whole backbone; stage B unfreezes its last two layers only.
        Returns the exact frozen/trainable record section 15 requires."""
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
        return {
            "stage": stage,
            "n_encoder_layers": len(self.encoder.encoder.layer),
            "unfrozen_encoder_parameters": unfrozen,
            "trainable_parameters": sum(p.numel() for p in self.parameters() if p.requires_grad),
            "frozen_parameters": sum(p.numel() for p in self.parameters()
                                     if not p.requires_grad),
        }

    def head_parameters(self):
        return list(self.projection.parameters()) + list(self.heads.parameters())

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
            "architecture": "FacetModel",
            "facets": list(FACETS),
            "backbone": self.backbone_name,
            "backbone_revision": self.backbone_revision,
            "hidden_size": int(self.config.hidden_size),
            "num_hidden_layers": int(self.config.num_hidden_layers),
            "pooling": "concat(first_token, attention_masked_mean)",
            "projection": f"Linear(2*{self.config.hidden_size}->{self.proj_dim}) GELU "
                          f"LayerNorm Dropout({self.dropout_p})",
            "head": f"Linear({self.proj_dim}->{self.head_dim}) GELU "
                    f"Dropout({self.dropout_p}) Linear({self.head_dim}->1)",
            "proj_dim": self.proj_dim,
            "head_dim": self.head_dim,
            "dropout": self.dropout_p,
            "output_activation": "identity (linear; the target is signed, Correction 1)",
            "scale": "none (Correction 1 removed SCALE)",
            "pair_format": "[CLS] tag [SEP] chunk [SEP], truncation=only_second",
        }
        cfg.update(extra or {})
        (out / "facet_config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        (out / "backbone_config.json").write_text(self.config.to_json_string(),
                                                  encoding="utf-8")
        if tokenizer is not None:
            tokenizer.save_pretrained(str(out))
        return out

    @classmethod
    def load(cls, path, device: str = "cpu"):
        """Rebuild from the artifact alone: the backbone architecture from the stored config,
        every weight from `model.safetensors`. No pretrained download of trained weights, no
        training data, no teacher."""
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoModel

        d = Path(path)
        cfg = json.loads((d / "facet_config.json").read_text(encoding="utf-8"))
        bb = AutoConfig.from_pretrained(str(d / "backbone_config.json"))
        encoder = AutoModel.from_config(bb)
        model = cls(backbone=cfg["backbone"], revision=cfg.get("backbone_revision"),
                    proj_dim=cfg["proj_dim"], head_dim=cfg["head_dim"],
                    dropout=cfg["dropout"], encoder=encoder)
        missing, unexpected = model.load_state_dict(
            load_file(str(d / "model.safetensors")), strict=False)
        if missing or unexpected:
            raise RuntimeError(f"facet model artifact mismatch: missing {missing[:5]}, "
                               f"unexpected {unexpected[:5]}")
        model.to(device).eval()
        return model, cfg


def load_tokenizer(path_or_name: str, revision: str | None = None):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(path_or_name), revision=revision)


def encode_pairs(tokenizer, tags: list, chunks: list, max_length: int):
    return tokenizer(tags, chunks, truncation="only_second", max_length=max_length,
                     padding=True, return_tensors="pt")
