"""The naming standard — one place that defines every rule.

Goal: make Python identifiers *typed and greppable* so structural search and code
maps become deterministic. A definition's kind is encoded in its name:

    py_class_<PascalName>      classes
    py_function_<snake_name>   module-level functions
    py_method_<snake_name>     methods (non-dunder)
    py_inst_<snake_class>      variables holding a class instance
    py_const_<UPPER_NAME>      module-level constants  (opt-in)

So `grep py_class_Cart` finds the class and every reference; `grep '^def py_function_'`
lists all functions; an instance `py_inst_cart = py_class_Cart()` ties the variable
back to its type by name alone — no resolver needed.

Rules:
* **Idempotent** — an already-prefixed name is left alone (safe to re-run).
* **Dunders exempt** — ``__init__``, ``__repr__``, ``__all__`` etc. are protocol
  names; never rewrite them.
* **Underscores preserved** — ``_helper`` → ``py_function__helper`` (still private
  by convention, still greppable).
"""

from __future__ import annotations

import re

PREFIX = {
    "class": "py_class_",
    "function": "py_function_",
    "method": "py_method_",
    "instance": "py_inst_",
    "const": "py_const_",
}
ALL_PREFIXES = tuple(PREFIX.values())

_DUNDER = re.compile(r"^__.*__$")
_UPPER = re.compile(r"^[A-Z][A-Z0-9_]*$")


def is_dunder(name: str) -> bool:
    return bool(_DUNDER.match(name))


def is_prefixed(name: str) -> bool:
    return name.startswith(ALL_PREFIXES)


def exempt(name: str) -> bool:
    """Names we never rename: dunders and already-prefixed identifiers."""
    return is_dunder(name) or is_prefixed(name)


def target_name(kind: str, name: str) -> str:
    """The conformant name for a definition of ``kind`` (idempotent)."""
    if exempt(name) or kind not in PREFIX:
        return name
    return PREFIX[kind] + name


def is_conformant(kind: str, name: str) -> bool:
    return exempt(name) or name == target_name(kind, name)


# --- instance naming -----------------------------------------------------

def _snake(name: str) -> str:
    """PascalCase/camelCase → snake_case (after stripping any class prefix)."""
    if name.startswith(PREFIX["class"]):
        name = name[len(PREFIX["class"]):]
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower().strip("_") or "obj"


def instance_name(class_name: str, descriptor: str = "") -> str:
    """The conformant variable name for an instance of ``class_name``."""
    base = PREFIX["instance"] + _snake(class_name)
    return f"{base}_{descriptor}" if descriptor else base


def is_conformant_instance(var_name: str, class_name: str) -> bool:
    # an instance var must start with py_inst_<snake_class>
    return exempt(var_name) or var_name.startswith(instance_name(class_name))


def describe() -> str:
    return ("py_class_<Pascal> · py_function_<snake> · py_method_<snake> · "
            "py_inst_<snake_class> · py_const_<UPPER>  (dunders exempt, idempotent)")
