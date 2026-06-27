"""Tests: the standard, the checker, and — critically — that a rename keeps the
code runnable (every reference updated consistently)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyprefix import standard, check, codemod  # noqa: E402

SRC = '''
TAX = 2

class Cart:
    def __init__(self):
        self.items = []

    def add(self, x):
        self.items.append(x)

    def total(self):
        return sum(self.items) * TAX


def make():
    c = Cart()
    c.add(3)
    c.add(4)
    return c.total()


result = make()
'''


def _run(source: str) -> dict:
    ns: dict = {}
    exec(compile(source, "<t>", "exec"), ns)   # noqa: S102 — test sandbox
    return ns


# --- standard ------------------------------------------------------------

def test_target_names():
    assert standard.target_name("class", "Cart") == "py_class_Cart"
    assert standard.target_name("function", "parse") == "py_function_parse"
    assert standard.target_name("method", "add") == "py_method_add"


def test_dunder_and_idempotent():
    assert standard.target_name("method", "__init__") == "__init__"        # exempt
    assert standard.target_name("class", "py_class_Cart") == "py_class_Cart"  # idempotent
    assert standard.is_conformant("function", "py_function_x")


def test_instance_name():
    assert standard.instance_name("Cart") == "py_inst_cart"
    assert standard.instance_name("py_class_HTTPClient") == "py_inst_http_client"


# --- checker -------------------------------------------------------------

def test_check_flags_violations():
    v = check.check_source(SRC, "m.py")
    kinds = {x["kind"] for x in v}
    assert "class" in kinds and "function" in kinds and "method" in kinds
    assert any(x["kind"] == "instance" and x["name"] == "c" for x in v)  # c = Cart()
    assert any(x["target"] == "py_class_Cart" for x in v)


# --- codemod keeps code runnable ----------------------------------------

def test_rename_preserves_behavior():
    baseline = _run(SRC)["result"]
    new, n = codemod.rename_source(SRC, methods=True, instances=False)
    assert n > 0
    ns = _run(new)                      # must still execute
    assert ns["result"] == baseline == 14
    assert "py_class_Cart" in new and "py_function_make" in new
    assert "py_method_add" in new and "c.py_method_add" in new
    assert "__init__" in new           # dunder untouched


def test_rename_with_instances():
    new, n = codemod.rename_source(SRC, methods=True, instances=True)
    assert _run(new)["result"] == 14
    assert "py_inst_cart = py_class_Cart()" in new
    assert "py_inst_cart.py_method_add(3)" in new


def test_idempotent():
    once, _ = codemod.rename_source(SRC, methods=True, instances=True)
    twice, n2 = codemod.rename_source(once, methods=True, instances=True)
    assert twice == once and n2 == 0          # second pass changes nothing


def test_check_clean_after_rename():
    new, _ = codemod.rename_source(SRC, methods=True, instances=True)
    # remaining: TAX (const) — not renamed by the codemod, still flagged
    left = [v for v in check.check_source(new) if v["kind"] != "const"]
    assert not left, left


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok", fn.__name__)
    print(f"\n{len(fns)} passed")
