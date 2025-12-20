"""Guardrail against importing resonance.legacy from non-legacy code."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _iter_python_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if "resonance/legacy" not in str(path)
        and "/tests/" not in str(path).replace("\\", "/")
    ]


def _imports_legacy(module: ast.AST) -> bool:
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "resonance.legacy" or alias.name.startswith("resonance.legacy."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "resonance.legacy" or node.module.startswith("resonance.legacy.")
            ):
                return True
    return False


def test_non_legacy_modules_do_not_import_legacy_package() -> None:
    legacy_root = Path("resonance") / "legacy"
    if not legacy_root.exists():
        pytest.skip("resonance.legacy does not exist")

    violations: list[str] = []
    scanned = list(_iter_python_files(Path("resonance")))
    assert scanned, "No resonance sources found to scan"
    for path in scanned:
        module = ast.parse(path.read_text(encoding="utf-8"))
        if _imports_legacy(module):
            violations.append(str(path))

    assert not violations, f"Non-legacy files import resonance.legacy: {violations}"
