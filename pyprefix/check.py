"""Deterministic conformance checker — the safe core.

Reports every definition and class-instance whose name doesn't follow the
standard, with an exact location and the conformant target name. No rewriting, so
it's safe to run anywhere (CI, pre-commit, a code-map gate). Instances are only
checked against classes defined in the same file, so stdlib instantiations like
``d = dict()`` are never flagged.
"""

from __future__ import annotations

import os

from . import standard
from .analyze import analyze


def _local_class(class_name: str, class_names: set) -> bool:
    # the instantiated name matches a class defined here (prefixed or not)
    return (class_name in class_names
            or standard.PREFIX["class"] + class_name in class_names
            or class_name.removeprefix(standard.PREFIX["class"]) in class_names)


def check_source(source: str, path: str = "<src>") -> list[dict]:
    try:
        a = analyze(source)
    except SyntaxError as e:
        return [{"path": path, "lineno": e.lineno or 0, "kind": "syntax",
                 "name": "", "target": "", "msg": str(e)}]
    out = []
    for d in a.defs:
        if not d.conformant:
            out.append({"path": path, "lineno": d.lineno, "kind": d.kind,
                        "name": d.name, "target": d.target,
                        "msg": f"{d.kind} '{d.name}' should be '{d.target}'"})
    for inst in a.instances:
        if not _local_class(inst.class_name, a.class_names):
            continue
        if not standard.is_conformant_instance(inst.var, inst.class_name):
            want = standard.instance_name(inst.class_name)
            out.append({"path": path, "lineno": inst.lineno, "kind": "instance",
                        "name": inst.var, "target": want,
                        "msg": f"instance '{inst.var}' of {inst.class_name} "
                               f"should start with '{want}'"})
    return out


def check_file(path: str) -> list[dict]:
    try:
        return check_source(open(path, encoding="utf-8", errors="replace").read(), path)
    except OSError:
        return []


def check_path(target: str, *, max_files: int = 2000) -> list[dict]:
    if os.path.isfile(target):
        return check_file(target)
    out, n = [], 0
    for dp, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")]
        for fn in sorted(files):
            if fn.endswith(".py"):
                out += check_file(os.path.join(dp, fn))
                n += 1
                if n >= max_files:
                    return out
    return out


def report(violations: list[dict]) -> str:
    if not violations:
        return "✓ all names conform to the standard"
    by_kind: dict[str, int] = {}
    for v in violations:
        by_kind[v["kind"]] = by_kind.get(v["kind"], 0) + 1
    lines = [f"{len(violations)} naming violations  "
             f"({', '.join(f'{k}: {n}' for k, n in sorted(by_kind.items()))})", ""]
    for v in sorted(violations, key=lambda v: (v["path"], v["lineno"])):
        loc = f"{os.path.basename(v['path'])}:{v['lineno']}"
        lines.append(f"  {loc:28} [{v['kind']}] {v['msg']}")
    return "\n".join(lines)
