"""pyprefix — typed, greppable Python names for deterministic search & code maps.

Encode each definition's kind in its name (py_class_/py_function_/py_method_/
py_inst_) so `grep py_class_Cart` finds the class and every use, and code maps
need no symbol resolver.

    from pyprefix import check, codemod, codemap, standard
    codemod.apply_file("mod.py")          # rename to the standard (verified)
    print(check.report(check.check_path("src")))
"""

from . import standard, check, codemod, codemap, analyze, graph, tools

__all__ = ["standard", "check", "codemod", "codemap", "analyze", "graph", "tools"]
__version__ = "0.1.0"
