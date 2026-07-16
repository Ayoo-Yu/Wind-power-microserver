import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _annotation_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                yield node.returns
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                arguments.append(node.args.vararg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg)
            for argument in arguments:
                if argument.annotation is not None:
                    yield argument.annotation
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


def test_python39_union_annotations_are_deferred():
    incompatible = []
    for path in BACKEND_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        uses_union = any(
            isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
            for annotation in _annotation_nodes(tree)
            for node in ast.walk(annotation)
        )
        if not uses_union:
            continue

        future_annotations = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in tree.body
        )
        if not future_annotations:
            incompatible.append(str(path.relative_to(BACKEND_ROOT)))

    assert incompatible == []
