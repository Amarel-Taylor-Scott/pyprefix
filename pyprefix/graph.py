"""Symbol/reference graph + visualization.

Because names are typed, the graph is exact: nodes are definitions (colored by
kind), edges are *contains* (class→method), *calls* (→function/method), and
*uses* (→class). A scope-aware walk attributes each reference to its innermost
enclosing definition, so edges mean "this symbol uses that symbol."

Exports three ways:
* **DOT** — Graphviz (`dot -Tsvg`),
* **Mermaid** — pastes into Markdown / renders inline on GitHub,
* **HTML** — a self-contained, dependency-free interactive force graph.
"""

from __future__ import annotations

import ast
import json
import os
from collections import defaultdict

from . import standard

_KIND_COLOR = {"class": "#d62728", "function": "#1f77b4", "method": "#2ca02c",
               "const": "#9467bd"}


def _defs_and_index(files: list[str]):
    nodes: dict[str, dict] = {}
    name_to_qual: dict[str, list] = defaultdict(list)
    trees: dict[str, ast.AST] = {}
    for path in files:
        try:
            src = open(path, encoding="utf-8", errors="replace").read()
            tree = ast.parse(src)
        except (OSError, SyntaxError):
            continue
        trees[path] = tree

        def reg(node, kind, qual):
            nodes[qual] = {"kind": kind, "name": qual.split(".")[-1],
                           "qual": qual, "file": os.path.basename(path),
                           "line": node.lineno}
            name_to_qual[qual.split(".")[-1]].append(qual)

        def walk(node, parent):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "method" if parent else "function"
                    qual = f"{parent}.{ch.name}" if parent else ch.name
                    reg(ch, kind, qual)
                    walk(ch, parent)
                elif isinstance(ch, ast.ClassDef):
                    qual = f"{parent}.{ch.name}" if parent else ch.name
                    reg(ch, "class", qual)
                    walk(ch, ch.name)
                else:
                    walk(ch, parent)
        walk(tree, "")
    return nodes, name_to_qual, trees


def build_graph(target: str, *, max_files: int = 2000) -> dict:
    files = _gather(target, max_files)
    nodes, name_to_qual, trees = _defs_and_index(files)
    edges: list[dict] = []
    seen = set()

    def add(src, dst, etype):
        if src and dst and src != dst and (src, dst, etype) not in seen:
            seen.add((src, dst, etype))
            edges.append({"src": src, "dst": dst, "type": etype})

    # contains: class → its methods
    for qual, n in nodes.items():
        if n["kind"] == "method":
            parent = qual.rsplit(".", 1)[0]
            if parent in nodes:
                add(parent, qual, "contains")

    # calls / uses: a reference inside def D matching another def's name.
    # cur_qual = innermost enclosing def (attributes the ref); class_parent =
    # innermost enclosing class (builds method qualnames to match the node index).
    def resolve(name):
        cands = name_to_qual.get(name, [])
        return cands[0] if len(cands) == 1 else None   # unambiguous only

    def walk(node, cur_qual, class_parent):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{class_parent}.{ch.name}" if class_parent else ch.name
                walk(ch, q, class_parent)
            elif isinstance(ch, ast.ClassDef):
                q = f"{class_parent}.{ch.name}" if class_parent else ch.name
                walk(ch, q, ch.name)
            else:
                if cur_qual:
                    tgt = None
                    if isinstance(ch, ast.Name):
                        tgt = resolve(ch.id)
                    elif isinstance(ch, ast.Attribute):
                        tgt = resolve(ch.attr)
                    if tgt and tgt in nodes and tgt != cur_qual:
                        et = "uses" if nodes[tgt]["kind"] == "class" else "calls"
                        add(cur_qual, tgt, et)
                walk(ch, cur_qual, class_parent)

    for tree in trees.values():
        walk(tree, "", "")

    for n in nodes.values():
        n["out"] = sum(1 for e in edges if e["src"] == n["qual"])
        n["in"] = sum(1 for e in edges if e["dst"] == n["qual"])
    return {"nodes": nodes, "edges": edges}


def _gather(target: str, max_files: int) -> list[str]:
    if os.path.isfile(target):
        return [target]
    out = []
    for dp, dirs, fs in os.walk(target):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("node_modules", "__pycache__", "venv", ".venv", "build", "dist")]
        for fn in sorted(fs):
            if fn.endswith(".py"):
                out.append(os.path.join(dp, fn))
        if len(out) >= max_files:
            break
    return out


# --- exporters -----------------------------------------------------------

def to_dot(g: dict) -> str:
    out = ["digraph symbols {", "  rankdir=LR; node [shape=box style=filled fontsize=10];"]
    for n in g["nodes"].values():
        color = _KIND_COLOR.get(n["kind"], "#888")
        out.append(f'  "{n["qual"]}" [label="{n["name"]}\\n{n["kind"]}" '
                   f'fillcolor="{color}33" color="{color}"];')
    style = {"contains": "dashed", "calls": "solid", "uses": "bold"}
    for e in g["edges"]:
        out.append(f'  "{e["src"]}" -> "{e["dst"]}" [style={style.get(e["type"],"solid")} '
                   f'label="{e["type"]}" fontsize=7];')
    out.append("}")
    return "\n".join(out)


def to_mermaid(g: dict) -> str:
    ids = {q: f"n{i}" for i, q in enumerate(g["nodes"])}
    shape = {"class": ("[[", "]]"), "function": ("(", ")"),
             "method": (">", "]"), "const": ("{{", "}}")}
    out = ["graph LR"]
    for q, n in g["nodes"].items():
        lo, ro = shape.get(n["kind"], ("[", "]"))
        out.append(f'  {ids[q]}{lo}"{n["name"]}"{ro}')
    arrow = {"contains": "-.->", "calls": "-->", "uses": "==>"}
    for e in g["edges"]:
        if e["src"] in ids and e["dst"] in ids:
            out.append(f'  {ids[e["src"]]} {arrow.get(e["type"],"-->")} {ids[e["dst"]]}')
    for kind, color in _KIND_COLOR.items():
        members = [ids[q] for q, n in g["nodes"].items() if n["kind"] == kind]
        if members:
            out.append(f"  classDef {kind} fill:{color}22,stroke:{color};")
            out.append(f"  class {','.join(members)} {kind};")
    return "\n".join(out)


def to_html(g: dict, *, title: str = "pyprefix symbol graph") -> str:
    data = json.dumps({
        "nodes": [{"id": q, "label": n["name"], "kind": n["kind"],
                   "deg": n["in"] + n["out"]} for q, n in g["nodes"].items()],
        "edges": [{"s": e["src"], "t": e["dst"], "type": e["type"]} for e in g["edges"]],
        "colors": _KIND_COLOR,
    })
    return _HTML.replace("__TITLE__", title).replace("__DATA__", data)


_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title>
<style>body{margin:0;font:13px system-ui;background:#0f1117;color:#ddd}
#h{padding:8px 12px;background:#161922}svg{width:100vw;height:calc(100vh - 40px)}
.lbl{font-size:10px;fill:#cfcfcf;pointer-events:none}line{stroke:#444}
.legend{font-size:11px}</style></head><body>
<div id="h"><b>__TITLE__</b> &middot; drag nodes &middot;
<span class=legend id=leg></span></div><svg id=s></svg><script>
const G=__DATA__,W=innerWidth,H=innerHeight-40;
const svg=document.getElementById('s');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
const N=G.nodes,E=G.edges,by={};N.forEach(n=>{n.x=Math.random()*W;n.y=Math.random()*H;n.vx=0;n.vy=0;by[n.id]=n;});
const leg=document.getElementById('leg');for(const k in G.colors){leg.innerHTML+=`<span style="color:${G.colors[k]}">&#9679; ${k}</span> `;}
function step(){for(const a of N){a.fx=0;a.fy=0;}
for(let i=0;i<N.length;i++)for(let j=i+1;j<N.length;j++){const a=N[i],b=N[j];let dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy)||1;const f=2200/(d*d);a.fx+=dx/d*f;a.fy+=dy/d*f;b.fx-=dx/d*f;b.fy-=dy/d*f;}
for(const e of E){const a=by[e.s],b=by[e.t];if(!a||!b)continue;let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1;const f=(d-90)*0.02;a.fx+=dx/d*f;a.fy+=dy/d*f;b.fx-=dx/d*f;b.fy-=dy/d*f;}
for(const a of N){if(a.drag)continue;a.vx=(a.vx+a.fx)*0.85;a.vy=(a.vy+a.fy)*0.85;a.x+=a.vx;a.y+=a.vy;a.x=Math.max(20,Math.min(W-20,a.x));a.y=Math.max(20,Math.min(H-20,a.y));a.fx+=(W/2-a.x)*0.002;a.fy+=(H/2-a.y)*0.002;}}
function draw(){let s='';for(const e of E){const a=by[e.s],b=by[e.t];if(!a||!b)continue;s+=`<line x1=${a.x} y1=${a.y} x2=${b.x} y2=${b.y} stroke-dasharray="${e.type=='contains'?'4':'0'}"/>`;}
for(const n of N){const r=5+Math.min(10,n.deg*1.5),c=G.colors[n.kind]||'#888';s+=`<circle cx=${n.x} cy=${n.y} r=${r} fill="${c}" stroke="#000" data-id="${n.id}"/><text class=lbl x=${n.x+r+2} y=${n.y+3}>${n.label}</text>`;}
svg.innerHTML=s;}
for(let i=0;i<400;i++)step();draw();
let drag=null;svg.addEventListener('mousedown',e=>{const id=e.target.getAttribute&&e.target.getAttribute('data-id');if(id){drag=by[id];drag.drag=1;}});
addEventListener('mousemove',e=>{if(drag){const r=svg.getBoundingClientRect();drag.x=(e.clientX-r.left)/r.width*W;drag.y=(e.clientY-r.top)/r.height*H;}});
addEventListener('mouseup',()=>{if(drag){drag.drag=0;drag=null;}});
(function loop(){step();draw();requestAnimationFrame(loop);})();
</script></body></html>"""
