"""pyprefix CLI — typed, greppable Python names.

    pyprefix check <path>                 # lint conformance (exit 1 if violations)
    pyprefix apply <path> [--instances] [--no-methods] [--dry-run]
    pyprefix map   <path> [--json map.json]
    pyprefix standard                     # print the naming standard
"""

from __future__ import annotations

import argparse
import sys

from . import standard, check, codemod, codemap


def cmd_check(a) -> int:
    v = check.check_path(a.path)
    print(check.report(v))
    return 1 if v else 0


def cmd_apply(a) -> int:
    res = codemod.apply_path(a.path, methods=not a.no_methods, instances=a.instances,
                             verify=not a.no_verify, write=not a.dry_run)
    total = sum(r["renames"] for r in res)
    changed = [r for r in res if r["changed"]]
    errs = [r for r in res if r.get("error")]
    verb = "would rename" if a.dry_run else "renamed"
    for r in changed:
        print(f"  {verb} {r['renames']:3} in {r['path']}")
    for r in errs:
        print(f"  ! {r['path']}: {r['error']}", file=sys.stderr)
    print(f"\n{verb} {total} identifiers across {len(changed)} files"
          + (" (dry run)" if a.dry_run else ""))
    if not a.dry_run and changed:
        left = check.check_path(a.path)
        print(f"post-apply check: {len(left)} violations remain "
              "(methods/instances called from other files need manual review)"
              if left else "post-apply check: ✓ all conform")
    return 0


def cmd_map(a) -> int:
    m = codemap.build(a.path)
    if a.json:
        codemap.to_json(m, a.json)
        print(f"map → {a.json} ({len(m)} symbols)", file=sys.stderr)
    print(codemap.report(m, top=a.top))
    return 0


def cmd_standard(a) -> int:
    print("pyprefix naming standard\n")
    print(standard.describe())
    print("\nExamples:")
    print("  class Cart            → py_class_Cart")
    print("  def parse_config()    → py_function_parse_config")
    print("  def add(self, x)      → py_method_add")
    print("  cart = py_class_Cart()→ py_inst_cart = py_class_Cart()")
    print("  __init__ / __repr__   → unchanged (dunders exempt)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pyprefix", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="lint names against the standard")
    p.add_argument("path"); p.set_defaults(fn=cmd_check)

    p = sub.add_parser("apply", help="rename to the standard (verified + rollback)")
    p.add_argument("path")
    p.add_argument("--no-methods", action="store_true", help="don't rename methods")
    p.add_argument("--instances", action="store_true", help="also rename class-instance vars")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("map", help="emit the typed code map")
    p.add_argument("path")
    p.add_argument("--json", help="write the map as JSON")
    p.add_argument("--top", type=int, default=0, help="limit per kind (0 = all)")
    p.set_defaults(fn=cmd_map)

    sub.add_parser("standard", help="print the naming standard").set_defaults(fn=cmd_standard)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
