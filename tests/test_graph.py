"""Tests for the graph builder, exporters, find, and stats."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyprefix import graph, tools  # noqa: E402

SRC = '''
class py_class_Cart:
    def py_method_add(self, x):
        return helper(x)

    def py_method_total(self):
        return 0


def helper(x):
    return x + 1


def py_function_run():
    c = py_class_Cart()
    return c.py_method_add(2)
'''


def _proj():
    d = tempfile.mkdtemp()
    open(os.path.join(d, "m.py"), "w").write(SRC)
    return d


def test_graph_nodes_and_kinds():
    g = graph.build_graph(_proj())
    kinds = {n["kind"] for n in g["nodes"].values()}
    assert {"class", "method", "function"} <= kinds
    assert "py_class_Cart" in g["nodes"]
    assert "py_class_Cart.py_method_add" in g["nodes"]


def test_graph_edges():
    g = graph.build_graph(_proj())
    etypes = {(e["src"], e["dst"], e["type"]) for e in g["edges"]}
    # class contains its method
    assert ("py_class_Cart", "py_class_Cart.py_method_add", "contains") in etypes
    # run() instantiates the class (uses) and calls add
    assert ("py_function_run", "py_class_Cart", "uses") in etypes
    # add() calls helper()
    assert any(s == "py_class_Cart.py_method_add" and d == "helper" and t == "calls"
               for s, d, t in etypes)


def test_exporters_nonempty_and_parseable():
    g = graph.build_graph(_proj())
    dot = graph.to_dot(g)
    assert dot.startswith("digraph") and "py_class_Cart" in dot
    mer = graph.to_mermaid(g)
    assert mer.startswith("graph LR") and "-->" in mer or "==>" in mer
    html = graph.to_html(g)
    assert "<svg" in html and "__DATA__" not in html   # template filled
    assert "py_class_Cart" in html                      # data embedded
    assert "force" not in html or "requestAnimationFrame" in html  # self-contained sim


def test_find_locates_symbol():
    hits = tools.find(_proj(), "Cart")
    assert "py_class_Cart" in hits
    assert hits["py_class_Cart"]["kind"] == "class"
    assert hits["py_class_Cart"]["ref_count"] >= 1   # referenced in run()


def test_stats_conformance():
    s = tools.stats(_proj())
    assert s["definitions"] >= 5
    assert s["def_violations"] == 1         # 'helper' is the one unprefixed function
    assert s["conformance"] == 0.8          # 4 of 5 defs conform
    assert "class" in s["by_kind"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok", fn.__name__)
    print(f"\n{len(fns)} passed")
