# pyprefix

> Make Python identifiers **typed and greppable** so structural search and code
> maps become *deterministic*. Encode each definition's kind in its name —
> `py_class_Cart`, `py_function_parse`, `py_method_add`, `py_inst_cart` — so
> `grep py_class_Cart` finds the class **and every reference**, `grep '^def py_function_'`
> lists all functions, and a code map needs no symbol resolver.

```
class Cart:                  →  class py_class_Cart:
    def add(self, x): ...    →      def py_method_add(self, x): ...
def open_cart():             →  def py_function_open_cart():
    c = Cart()               →      py_inst_cart = py_class_Cart()
    c.add(1)                 →      py_inst_cart.py_method_add(1)
__init__ / __repr__          →  unchanged (dunders exempt)
```

## Why

Resolving "what is this name?" in Python normally needs scope/type analysis.
If the name *says* what it is, that analysis is free — grep is exact, codemaps
are unambiguous, and deterministic checks (CI gates, refactor tools, the
[hybrid-graph-mapper](https://github.com/Amarel-Taylor-Scott/hybrid-graph-mapper)
/ [contradiction-mapper](https://github.com/Amarel-Taylor-Scott/contradiction-mapper))
get a clean, typed symbol stream to work from.

## The standard

| Kind | Pattern | Example |
|---|---|---|
| class | `py_class_<Pascal>` | `py_class_HTTPClient` |
| function | `py_function_<snake>` | `py_function_parse_config` |
| method | `py_method_<snake>` | `py_method_add_item` |
| instance | `py_inst_<snake_class>` | `py_inst_http_client` |
| constant | `py_const_<UPPER>` | `py_const_MAX_RETRIES` |

**Idempotent** (safe to re-run), **dunders exempt** (`__init__` etc. are never
touched), **underscores preserved** (`_helper` → `py_function__helper`).

## Three modes

```bash
pyprefix check  ./src                 # lint conformance — exit 1 if violations (safe; CI-ready)
pyprefix apply  ./src [--instances]   # rename to the standard, verified + rollback
pyprefix map    ./src [--json m.json] # typed symbol map: each def + its references
pyprefix standard                     # print the convention
```

- **`check`** — deterministic, read-only. The foundation: every non-conforming
  definition/instance with its location and the target name.
- **`apply`** — the codemod. Edits identifiers by exact position so **formatting,
  comments, and strings are untouched**, then **`compile()`-verifies and rolls
  back** if a rewrite wouldn't parse — it can never leave broken syntax. Renames
  functions, classes, methods (+ `--instances` for instance vars) and updates
  their in-file references so the code keeps working (the test suite proves a
  renamed module still executes to the same result).
- **`map`** — the payoff: a typed symbol index (def + reference locations), exact
  because the names are typed.

## Scope & honesty

Functions and classes rename safely (bare-name references resolve within a file).
Methods and instances also rewrite their in-file references — **complete for
self-contained files** (what gets shipped most), but references in *other* files
to a duck-typed `obj.method` can't be resolved by static analysis, so for
multi-file codebases lead with `check` and review, or run `apply` per package and
re-run your tests (the `compile()` gate guarantees syntactic safety, not semantic
equivalence across modules). Python today; the convention generalizes.

## Library

```python
from pyprefix import check, codemod, codemap
print(check.report(check.check_path("src")))      # lint
codemod.apply_file("mod.py", instances=True)       # rename (verified)
codemap.to_json(codemap.build("src"), "map.json")  # typed symbol map
```

## Layout

```
pyprefix/
  standard.py   the convention: prefixes, exemptions, instance naming (one source of truth)
  analyze.py    AST → definitions / references / instances with positions
  check.py      deterministic conformance linter
  codemod.py    position-guided rewrite + compile-verify + rollback
  codemap.py    typed symbol map (markdown + JSON)
  cli.py        check / apply / map / standard
```

MIT. Stdlib-only.
