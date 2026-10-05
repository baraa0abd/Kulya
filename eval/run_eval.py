"""Extraction evaluation over the golden set.

    cd backend
    python ../eval/run_eval.py --client mock        # harness sanity check: must score 1.0
    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=... python ../eval/run_eval.py --client anthropic

Scores symptoms and access_findings by `code` per note (multiset match), plus invalid-rate and the
number of evidence failures. Writes eval/report.md. No database is used.
"""

# ruff: noqa: E402
import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kulya.settings")

import django

django.setup()

from ai_engine.client import (
    AnthropicLLMClient,
    LLMClient,
    LLMOutputError,
    MockLLMClient,
    fixture_key,
)
from ai_engine.services import (
    EXTRACTION_PROMPT,
    extraction_user_input,
    load_prompt,
)
from ai_engine.validators import load_schema, validate_extraction

GOLDEN = ROOT / "eval" / "golden" / "golden.json"
SCORED_FIELDS = ["symptoms", "access_findings"]


def load_golden() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def perfect_mock_client(golden: list[dict], directory: Path) -> MockLLMClient:
    """A MockLLMClient whose fixtures are exactly the expected outputs (harness sanity check)."""
    folder = directory / EXTRACTION_PROMPT
    folder.mkdir(parents=True, exist_ok=True)
    for case in golden:
        path = folder / f"{fixture_key(extraction_user_input(case['note']))}.json"
        path.write_text(json.dumps(case["expected"], ensure_ascii=False), encoding="utf-8")
    return MockLLMClient(fixtures_dir=directory)


def evaluate(client: LLMClient, golden: list[dict]) -> dict:
    counts = {f: Counter() for f in SCORED_FIELDS}  # tp / fp / fn per field
    invalid = evidence_failures = 0
    rows = []
    for case in golden:
        errors: list[dict] = []
        payload: dict = {}
        try:
            payload = client.complete_json(
                EXTRACTION_PROMPT,
                load_prompt(EXTRACTION_PROMPT),
                extraction_user_input(case["note"]),
                load_schema(EXTRACTION_PROMPT),
            )
            ok, errors = validate_extraction(payload, case["note"])
        except LLMOutputError as exc:
            ok, errors = False, [{"code": "llm_output_error", "message": str(exc)}]
        invalid += not ok
        evidence_failures += sum(e["code"] == "evidence_not_found" for e in errors)
        row = {"id": case["id"], "valid": ok, "errors": [e["code"] for e in errors]}
        for field in SCORED_FIELDS:
            expected = Counter(item["code"] for item in case["expected"][field])
            # An invalid draft never reaches a nurse, so it contributes no predictions (only misses).
            items = payload.get(field, []) if ok else []
            predicted = Counter(item["code"] for item in items)
            tp = sum((expected & predicted).values())
            counts[field].update(tp=tp, fp=sum(predicted.values()) - tp, fn=sum(expected.values()) - tp)
            row[field] = {
                "expected": sorted(expected.elements()),
                "predicted": sorted(predicted.elements()),
            }
        rows.append(row)

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 1.0

    metrics = {
        field: {
            "precision": ratio(c["tp"], c["tp"] + c["fp"]),
            "recall": ratio(c["tp"], c["tp"] + c["fn"]),
            **{k: c[k] for k in ("tp", "fp", "fn")},
        }
        for field, c in counts.items()
    }
    return {
        "model": client.model_name,
        "notes": len(golden),
        "metrics": metrics,
        "invalid": invalid,
        "invalid_rate": ratio(invalid, len(golden)) if golden else 0.0,
        "evidence_failures": evidence_failures,
        "rows": rows,
    }


def render_report(result: dict) -> str:
    lines = [
        "# Extraction evaluation report",
        "",
        f"- Date: {dt.date.today().isoformat()}",
        f"- Model: `{result['model']}`",
        f"- Prompt: `{EXTRACTION_PROMPT}`",
        f"- Golden notes: {result['notes']} (synthetic, Iraqi dialect)",
        "",
        "| Field | Precision | Recall | TP | FP | FN |",
        "|---|---|---|---|---|---|",
    ]
    for field, m in result["metrics"].items():
        lines.append(f"| {field} | {m['precision']:.2f} | {m['recall']:.2f} | {m['tp']} | {m['fp']} | {m['fn']} |")
    lines += [
        "",
        f"- Invalid drafts: {result['invalid']} / {result['notes']} ({result['invalid_rate']:.0%})",
        f"- Evidence failures caught by the validator: {result['evidence_failures']}",
        "- Accepted drafts with ungrounded spans: 0 (the validator rejects them by construction)",
        "",
        "Scoring is by `code` per note. Invalid drafts count as misses, never as predictions.",
        "",
        "## Notes that differ from the golden annotation",
        "",
    ]
    differing = [
        r for r in result["rows"] if not r["valid"] or any(r[f]["expected"] != r[f]["predicted"] for f in SCORED_FIELDS)
    ]
    for r in differing:
        detail = "; ".join(f"{f}: expected {r[f]['expected']} got {r[f]['predicted']}" for f in SCORED_FIELDS)
        lines.append(f"- {r['id']} (valid={r['valid']}, errors={r['errors']}): {detail}")
    if not differing:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=["mock", "anthropic"], default="mock")
    parser.add_argument("--out", default=str(ROOT / "eval" / "report.md"))
    args = parser.parse_args()
    golden = load_golden()
    with tempfile.TemporaryDirectory() as tmp:
        client = AnthropicLLMClient() if args.client == "anthropic" else perfect_mock_client(golden, Path(tmp))
        result = evaluate(client, golden)
    Path(args.out).write_text(render_report(result), encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    for field, m in result["metrics"].items():
        print(f"{field}: precision={m['precision']:.2f} recall={m['recall']:.2f}")
    print(f"invalid={result['invalid']} evidence_failures={result['evidence_failures']}")


if __name__ == "__main__":
    main()
