"""The codemod — rename definitions and their in-file references in place.

Edits are applied by exact (line, column) span, so formatting, comments, and
strings are untouched — only identifiers move. Every rewrite is compiled before
it's written; if it wouldn't parse, the file is left exactly as it was (rollback).

Scope + honesty: functions and classes rename safely (bare-name references within
the file). Methods (`--methods`, default on) and instances (`--instances`,
opt-in) rename their in-file references too, which is complete for self-contained
files (what this ecosystem mostly ships) but can miss references in *other* files
— so for multi-file code, lead with ``check`` and review. ``compile()`` verify
guarantees we never write something that won't parse.
"""

from __future__ import annotations

import re
from collections import defaultdict

from . import standard
from .analyze import analyze
from .check import _local_class


def _apply_edits(lines: list[str], edits: list[tuple]) -> list[str]:
    by_line: dict[int, list] = defaultdict(list)
    for ln, a, b, t in edits:
        by_line[ln].append((a, b, t))
    for ln, es in by_line.items():
        line = lines[ln - 1]
        for a, b, t in sorted(es, key=lambda e: -e[0]):   # right-to-left
            line = line[:a] + t + line[b:]
        lines[ln - 1] = line
    return lines


def rename_source(source: str, *, functions: bool = True, classes: bool = True,
                  methods: bool = True, instances: bool = False) -> tuple[str, int]:
    a = analyze(source)
    fc_map = {d.name: d.target for d in a.defs if not d.conformant
              and ((d.kind == "function" and functions) or (d.kind == "class" and classes))}
    m_map = {d.name: d.target for d in a.defs
             if d.kind == "method" and methods and not d.conformant}
    inst_map: dict[str, str] = {}
    if instances:
        for inst in a.instances:
            if _local_class(inst.class_name, a.class_names) \
                    and not standard.is_conformant_instance(inst.var, inst.class_name):
                inst_map[inst.var] = standard.instance_name(inst.class_name)

    if not (fc_map or m_map or inst_map):
        return source, 0

    lines = source.split("\n")
    edits: list[tuple] = []

    # definition name tokens (regex on the def/class line — unambiguous there)
    for d in a.defs:
        tgt = fc_map.get(d.name) or m_map.get(d.name)
        if not tgt:
            continue
        kw = "class" if d.kind == "class" else "def"
        m = re.search(rf"\b{kw}\s+({re.escape(d.name)})\b", lines[d.lineno - 1])
        if m:
            edits.append((d.lineno, m.start(1), m.end(1), tgt))

    # bare-name references → functions/classes (and instance vars, if enabled)
    for r in a.name_refs:
        if r.name in fc_map:
            edits.append((r.lineno, r.col, r.end_col, fc_map[r.name]))
        elif r.name in inst_map:
            edits.append((r.lineno, r.col, r.end_col, inst_map[r.name]))

    # attribute references → methods (self.x / cls.x / obj.x within the file)
    for r in a.attr_refs:
        if r.attr in m_map:
            edits.append((r.end_lineno, r.end_col - len(r.attr), r.end_col, m_map[r.attr]))

    new = "\n".join(_apply_edits(lines, edits))
    return new, len(edits)


def apply_file(path: str, *, methods: bool = True, instances: bool = False,
               verify: bool = True, write: bool = True) -> dict:
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as e:
        return {"path": path, "renames": 0, "changed": False, "error": str(e)}
    new, n = rename_source(src, methods=methods, instances=instances)
    if n == 0 or new == src:
        return {"path": path, "renames": 0, "changed": False}
    if verify:
        try:
            compile(new, path, "exec")            # never write something that won't parse
        except SyntaxError as e:
            return {"path": path, "renames": 0, "changed": False,
                    "error": f"verify failed, rolled back: {e}"}
    if write:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return {"path": path, "renames": n, "changed": True}


def apply_path(target: str, **kw) -> list[dict]:
    import os
    if os.path.isfile(target):
        return [apply_file(target, **kw)]
    out = []
    for dp, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")]
        for fn in sorted(files):
            if fn.endswith(".py"):
                out.append(apply_file(os.path.join(dp, fn), **kw))
    return out
