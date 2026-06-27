"""Small tools that the typed names make exact: find-a-symbol and project stats."""

from __future__ import annotations

from . import codemap, check, standard


def _matches(symbol: str, query: str) -> bool:
    if query in (symbol,):
        return True
    base = symbol
    for p in standard.ALL_PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    return query == base or query.lower() in symbol.lower()


def find(target: str, query: str) -> dict:
    """Every definition + reference of a symbol (exact, because names are typed)."""
    m = codemap.build(target)
    return {n: v for n, v in m.items() if _matches(n, query)}


def find_report(hits: dict) -> str:
    if not hits:
        return "no matching symbols"
    out = []
    for name, v in sorted(hits.items(), key=lambda kv: -kv[1]["ref_count"]):
        out.append(f"{name}  ({v['kind']})")
        for d in v["defs"]:
            out.append(f"  def  {d}")
        for r in v["refs"][:50]:
            out.append(f"  ref  {r}")
        if len(v["refs"]) > 50:
            out.append(f"  … +{len(v['refs']) - 50} more refs")
    return "\n".join(out)


def _count_defs(target: str) -> tuple[int, dict]:
    """Per-occurrence definition count (so it lines up with per-occurrence
    violations — a name defined in 3 files counts 3 times, like the checker)."""
    import os
    from .analyze import analyze
    total, kinds = 0, {}
    files = [target] if os.path.isfile(target) else [
        os.path.join(dp, fn)
        for dp, dirs, fs in os.walk(target)
        if not any(part.startswith(".") or part in
                   ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")
                   for part in dp.split(os.sep))
        for fn in fs if fn.endswith(".py")]
    for f in files:
        try:
            a = analyze(open(f, encoding="utf-8", errors="replace").read())
        except (OSError, SyntaxError):
            continue
        for d in a.defs:
            if d.kind in ("class", "function", "method", "const"):
                total += 1
                kinds[d.kind] = kinds.get(d.kind, 0) + 1
    return total, kinds


def stats(target: str) -> dict:
    m = codemap.build(target)
    violations = check.check_path(target)
    total_defs, kinds = _count_defs(target)
    def_viol = [x for x in violations if x["kind"] in ("class", "function", "method", "const")]
    conformance = max(0.0, (total_defs - len(def_viol)) / total_defs) if total_defs else 1.0
    top = sorted(m.items(), key=lambda kv: -kv[1]["ref_count"])[:10]
    return {"symbols": len(m), "definitions": total_defs, "by_kind": kinds,
            "violations": len(violations), "def_violations": len(def_viol),
            "conformance": round(conformance, 3),
            "top_referenced": [(n, v["ref_count"]) for n, v in top]}


def stats_report(s: dict) -> str:
    out = [f"symbols: {s['symbols']}  ·  conformance: {int(s['conformance']*100)}%  "
           f"·  violations: {s['violations']}"]
    out.append("by kind: " + ", ".join(f"{k}:{v}" for k, v in sorted(s["by_kind"].items())))
    out.append("most referenced:")
    for n, c in s["top_referenced"]:
        if c:
            out.append(f"  {c:4}  {n}")
    return "\n".join(out)
