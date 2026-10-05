"""Generate docs/api.md from the OpenAPI schema. Run: python gen_api_md.py (or `make docs`)."""

import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kulya.settings")
django.setup()

from drf_spectacular.generators import SchemaGenerator  # noqa: E402

schema = SchemaGenerator().get_schema(request=None, public=True)
lines = [
    "# Kulya API",
    "",
    "Generated from the OpenAPI schema by `backend/gen_api_md.py` — do not edit by hand.",
    "Live schema: `GET /api/schema/`, Swagger UI: `GET /api/docs/`.",
    "",
    'Errors always use: `{"error": {"code", "message_ar", "message_en", "details"}}`.',
    "",
    "| Method | Path | Request body | Response | Notes |",
    "|---|---|---|---|---|",
]


def ref(node: dict) -> str:
    content = node.get("content", {}).get("application/json", {}).get("schema", {})
    many = content.get("type") == "array"
    name = (content.get("items", content)).get("$ref", "").rsplit("/", 1)[-1]
    return f"`{name}{'[]' if many else ''}`" if name else "—"


for path, operations in schema["paths"].items():
    for method, op in operations.items():
        ok = next(iter(op["responses"].values()))
        params = ", ".join(f"`?{p['name']}=`" for p in op.get("parameters", []) if p["in"] == "query")
        notes = " ".join(f"{op.get('description', '')} {params}".split())
        lines.append(f"| {method.upper()} | `{path}` | {ref(op.get('requestBody', {}))} | {ref(ok)} | {notes} |")

lines += ["", "## Schemas", ""]
for name, component in schema["components"]["schemas"].items():
    lines.append(f"### {name}")
    for field, spec in component.get("properties", {}).items():
        kind = spec.get("type") or spec.get("$ref", "").rsplit("/", 1)[-1] or "any"
        enum = f" ({' | '.join(map(str, component['enum']))})" if "enum" in component else ""
        lines.append(f"- `{field}`: {kind}{enum}{' (read-only)' if spec.get('readOnly') else ''}")
    if "enum" in component:
        lines.append("- one of: " + " | ".join(f"`{v}`" for v in component["enum"]))
    lines.append("")

out = Path(__file__).resolve().parent.parent / "docs" / "api.md"
out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
print(f"wrote {out}")
