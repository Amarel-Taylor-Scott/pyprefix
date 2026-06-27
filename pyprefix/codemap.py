"""Typed code map — the payoff of the convention.

Because each name encodes its kind and is (after `apply`) unique and greppable,
the map is exact: for every definition we list its location and every reference
location, grouped by kind. No symbol resolver, no heuristics — just the typed
names. `grep py_class_Cart` would give you the same set; this assembles it for the
whole tree at once (and as JSON for tooling).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from .analyze import analyze


def build(target: str, *, max_files: int = 2000) -> dict:
    files = []
    if os.path.isfile(target):
        files = [target]
    else:
        for dp, dirs, fs in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".")
                       and d not in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")]
            for fn in sorted(fs):
                if fn.endswith(".py"):
                    files.append(os.path.join(dp, fn))
            if len(files) >= max_files:
                break

    symbols: dict[str, dict] = defaultdict(
        lambda: {"kind": "", "defs": [], "refs": []})
    for path in files:
        try:
            a = analyze(open(path, encoding="utf-8", errors="replace").read())
        except (OSError, SyntaxError):
            continue
        rel = os.path.relpath(path, target if os.path.isdir(target) else os.path.dirname(target) or ".")
        for d in a.defs:
            symbols[d.name]["kind"] = d.kind
            symbols[d.name]["defs"].append(f"{rel}:{d.lineno}")
        for r in a.name_refs:
            if r.name in symbols or True:
                symbols[r.name]["refs"].append(f"{rel}:{r.lineno}")
        for r in a.attr_refs:
            symbols[r.attr]["refs"].append(f"{rel}:{r.end_lineno}")

    # keep only symbols that have a definition (drop stray name hits)
    out = {n: v for n, v in symbols.items() if v["defs"]}
    for v in out.values():
        v["ref_count"] = len(v["refs"])
    return out


def report(symbols: dict, *, top: int = 0) -> str:
    by_kind: dict[str, list] = defaultdict(list)
    for name, v in symbols.items():
        by_kind[v["kind"]].append((name, v))
    order = ["class", "function", "method", "const"]
    lines = [f"# Typed code map — {len(symbols)} symbols", ""]
    for kind in order + [k for k in by_kind if k not in order]:
        items = sorted(by_kind.get(kind, []), key=lambda kv: -kv[1]["ref_count"])
        if not items:
            continue
        lines.append(f"## {kind} ({len(items)})")
        for name, v in (items[:top] if top else items):
            d = v["defs"][0] if v["defs"] else "?"
            lines.append(f"- `{name}`  def `{d}`  ·  {v['ref_count']} refs")
        lines.append("")
    return "\n".join(lines)


def to_json(symbols: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(symbols, f, indent=2, ensure_ascii=False)
