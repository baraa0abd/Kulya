"""Dependency rules that keep arithmetic pure and provider calls behind one boundary."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def imported_modules(file: Path) -> list[str]:
    tree = ast.parse(file.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return imports


def test_nutrition_arithmetic_has_no_framework_or_infrastructure_dependencies():
    imports = imported_modules(ROOT / "nutrition/engine.py")
    assert set(imports) <= {"collections", "datetime"}


def test_nutrition_does_not_depend_on_clinical_ai_workflows():
    for file in (ROOT / "nutrition").glob("*.py"):
        assert "ai.services" not in imported_modules(file), file.name


def test_application_code_calls_models_through_gateway():
    for app in ("clinical", "workflow", "nutrition", "assistant"):
        for file in (ROOT / app).glob("*.py"):
            assert "ai.provider" not in imported_modules(file), file.name


def test_assistant_wording_and_validation_stay_free_of_database_and_framework():
    imports = imported_modules(ROOT / "assistant/ai.py")
    assert not [m for m in imports if m.startswith(("django", "rest_framework")) or m.endswith("models")]
