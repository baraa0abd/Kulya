"""Retrieval over approved, versioned protocol passages stored in pgvector."""

import hashlib
import math
import re
from datetime import date

from django.conf import settings
from django.db.models import Q
from pgvector.django import CosineDistance

from core.models import Organization

from .models import ClinicalProtocol, ProtocolChunk, ProtocolVersion

_TOKEN = re.compile(r"[a-z0-9؀-ۿ]+")
_STOP = {"the", "a", "an", "of", "and", "or", "to", "is", "in", "for", "be", "with", "on", "as", "at", "by", "must"}


class HashingEmbedder:
    """ponytail: deterministic feature-hashing embedding (lexical overlap, not meaning). It needs no
    network or key, which keeps tests and the offline demo reproducible. Swap in a real embedding
    model behind `embed()` before relying on retrieval quality."""

    name = "hashing-256"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * settings.EMBEDDING_DIMENSIONS
        for token in _TOKEN.findall(text.lower().replace("_", " ")):
            if token in _STOP or len(token) < 3:
                continue
            digest = hashlib.blake2b(token[:6].encode(), digest_size=4).digest()  # crude stemming by prefix
            vector[int.from_bytes(digest, "big") % len(vector)] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]


def get_embedder() -> HashingEmbedder:
    return HashingEmbedder()


def chunk_markdown(text: str) -> list[tuple[str, str]]:
    """Split on '## ' headings into (section, passage)."""
    chunks, section, lines = [], "Overview", []
    for line in text.splitlines():
        if line.startswith("## "):
            if "".join(lines).strip():
                chunks.append((section, "\n".join(lines).strip()))
            section, lines = line[3:].strip(), []
        elif not line.startswith("# "):
            lines.append(line)
    if "".join(lines).strip():
        chunks.append((section, "\n".join(lines).strip()))
    return chunks


def ingest_protocol(
    organization: Organization,
    title: str,
    version: str,
    text: str,
    *,
    owner: str,
    effective: date,
    expiry: date | None = None,
    approval: str = ProtocolVersion.Approval.APPROVED,
    is_synthetic: bool = True,
) -> ProtocolVersion:
    """Idempotent: re-ingesting the same title + version replaces its chunks."""
    protocol, _ = ClinicalProtocol.objects.get_or_create(
        organization=organization, title=title, defaults={"clinical_owner": owner, "is_synthetic": is_synthetic}
    )
    pv, _ = ProtocolVersion.objects.update_or_create(
        protocol=protocol,
        version=version,
        defaults={"text": text, "approval_status": approval, "effective_date": effective, "expiry_date": expiry},
    )
    pv.chunks.all().delete()
    embedder = get_embedder()
    ProtocolChunk.objects.bulk_create(
        ProtocolChunk(
            protocol_version=pv, section=section, text=passage, embedding=embedder.embed(f"{section}\n{passage}")
        )
        for section, passage in chunk_markdown(text)
    )
    return pv


def retrieve(organization_id, query: str, today: date | None = None) -> list[dict]:
    """Top passages for `query`, restricted to this organization's approved and currently effective
    protocol versions. Returns [] when nothing is similar enough: callers must then report
    insufficient_protocol_evidence rather than cite anything."""
    today = today or date.today()
    if not query.strip():
        return []
    distance = CosineDistance("embedding", get_embedder().embed(query))
    chunks = (
        ProtocolChunk.objects.filter(
            Q(protocol_version__expiry_date__isnull=True) | Q(protocol_version__expiry_date__gt=today),
            protocol_version__protocol__organization_id=organization_id,
            protocol_version__approval_status=ProtocolVersion.Approval.APPROVED,
            protocol_version__effective_date__lte=today,
        )
        .annotate(distance=distance)
        .select_related("protocol_version__protocol")
        .order_by("distance")[: settings.RAG_TOP_K]
    )
    return [
        {
            "id": str(chunk.id),
            "document_id": str(chunk.protocol_version.protocol_id),
            "title": chunk.protocol_version.protocol.title,
            "protocol_version": chunk.protocol_version.version,
            "section": chunk.section,
            "text": chunk.text,
            "similarity": round(1 - chunk.distance, 4),
            "is_synthetic": chunk.protocol_version.protocol.is_synthetic,
        }
        for chunk in chunks
        if 1 - chunk.distance >= settings.RAG_MIN_SIMILARITY
    ]


def retrieval_query(ctx: dict, findings: list[dict]) -> str:
    """What this session is about, in words: its event and action types plus the check names."""
    parts = [e["event_type"] for e in ctx["events"]] + [a["action_type"] for a in ctx["nursing_actions"]]
    parts += [f["check"] for f in findings]
    return " ".join(sorted(set(parts))).replace("_", " ")
