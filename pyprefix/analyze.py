"""AST analysis — find every definition, reference, and instance, with positions.

One pass over a file yields: the definitions to rename (functions/classes/methods/
constants), the reference identifiers that point at them (so the codemod can update
call sites), and the class-instance assignments (so the checker can enforce
instance naming). Positions are kept so the rewrite can edit identifiers in place
without disturbing formatting, comments, or strings.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from . import standard


@dataclass
class Definition:
    kind: str            # function | class | method | const
    name: str
    qualname: str
    lineno: int
    parent_class: str | None = None

    @property
    def conformant(self) -> bool:
        return standard.is_conformant(self.kind, self.name)

    @property
    def target(self) -> str:
        return standard.target_name(self.kind, self.name)


@dataclass
class NameRef:
    name: str
    lineno: int
    col: int
    end_col: int


@dataclass
class AttrRef:
    attr: str
    end_lineno: int
    end_col: int


@dataclass
class InstanceAssign:
    var: str
    class_name: str
    lineno: int


@dataclass
class Analysis:
    defs: list = field(default_factory=list)
    name_refs: list = field(default_factory=list)
    attr_refs: list = field(default_factory=list)
    instances: list = field(default_factory=list)
    class_names: set = field(default_factory=set)
    method_names: set = field(default_factory=set)

    def rename_map(self, *, methods: bool = True) -> dict:
        m = {}
        for d in self.defs:
            if d.kind == "method" and not methods:
                continue
            if d.kind in ("function", "class", "method") and not d.conformant:
                m[d.name] = d.target
        return m


def analyze(source: str) -> Analysis:
    tree = ast.parse(source)
    a = Analysis()

    def visit(node, parent_class: str | None, top: bool):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if parent_class else "function"
                qn = f"{parent_class}.{ch.name}" if parent_class else ch.name
                a.defs.append(Definition(kind, ch.name, qn, ch.lineno, parent_class))
                if kind == "method":
                    a.method_names.add(ch.name)
                visit(ch, parent_class, False)
            elif isinstance(ch, ast.ClassDef):
                a.defs.append(Definition("class", ch.name, ch.name, ch.lineno))
                a.class_names.add(ch.name)
                visit(ch, ch.name, False)
            elif isinstance(ch, ast.Assign) and top:
                # module-level CONSTANT (UPPER name) + class-instance assignment
                for t in ch.targets:
                    if isinstance(t, ast.Name) and standard._UPPER.match(t.id):
                        a.defs.append(Definition("const", t.id, t.id, ch.lineno))
                _record_instance(a, ch)
                visit(ch, parent_class, top)
            else:
                if isinstance(ch, ast.Assign):
                    _record_instance(a, ch)
                visit(ch, parent_class, False if not isinstance(ch, ast.Module) else top)

    visit(tree, None, True)

    # references (whole-tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            a.name_refs.append(NameRef(node.id, node.lineno, node.col_offset,
                                       getattr(node, "end_col_offset", node.col_offset)))
        elif isinstance(node, ast.Attribute):
            ec = getattr(node, "end_col_offset", None)
            el = getattr(node, "end_lineno", node.lineno)
            if ec is not None:
                a.attr_refs.append(AttrRef(node.attr, el, ec))
    return a


def _record_instance(a: Analysis, assign: ast.Assign) -> None:
    v = assign.value
    if isinstance(v, ast.Call):
        cls = getattr(v.func, "id", None) or getattr(v.func, "attr", None)
        if cls:
            for t in assign.targets:
                if isinstance(t, ast.Name):
                    a.instances.append(InstanceAssign(t.id, cls, assign.lineno))
