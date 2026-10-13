#!/usr/bin/env python3
"""Reject mixing a native substrate with an incompatible product assembler."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_pins(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == "PINS" for n in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Missing product source pins")

def validate(pins: dict[str, str], workflow: str) -> None:
    repositories = {"runtime": "RiscRTE", "shared": "RiscRTE-Watch", "controllers": "RiscRTE-T-Watch-S3", "generic": "RiscRTE-Drivers", "system": "RiscRTE-System-Apps", "utilities": "RiscRTE-Utilities"}
    checkout = dict(re.findall(r"repository: michaelrolphone-cmyk/([^\s]+)\s+ref: ([0-9a-f]{40})", workflow))
    for key, repository in repositories.items():
        if checkout.get(repository) != pins[key]:
            raise ValueError(f"{key}: workflow/assembler source mismatch")

if __name__ == "__main__":
    pins = read_pins((ROOT / "scripts/build_boot_test.py").read_text())
    workflow = (ROOT / ".github/workflows/boot-test.yml").read_text()
    validate(pins, workflow)
    metadata = json.loads((ROOT / "hardware/providers.json").read_text())
    if metadata["native_source"] != pins["runtime"]:
        raise ValueError("Board provider metadata selects an incompatible native source")
    # The stale native substrate from 0.1.2 cannot materialize the new PMIC function.
    broken = workflow.replace(pins["runtime"], "5323d1e834bdcc8e5e9fb0e8f76c383e46626801")
    try:
        validate(pins, broken)
    except ValueError:
        pass
    else:
        raise AssertionError("Stale native source was not rejected")
    print("Boot composition: all six checkouts and board metadata match; stale native pin rejected")
