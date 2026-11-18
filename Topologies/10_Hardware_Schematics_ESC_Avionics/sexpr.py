"""Minimal s-expression reader/writer for KiCad files (symbols, schematics, netlists)."""
import re

TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """An unquoted atom (keyword or number) as opposed to a quoted string."""


def parse(text):
    stack, cur = [], []
    for m in TOKEN.finditer(text):
        op, cl, qs, at = m.groups()
        if op: stack.append(cur); cur = []
        elif cl: done = cur; cur = stack.pop(); cur.append(done)
        elif qs is not None: cur.append(qs[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        elif at is not None: cur.append(Sym(at))
    return cur


def dump(x, ind=0):
    if isinstance(x, list):
        if not x: return "()"
        simple = all(not isinstance(e, list) for e in x)
        if simple and len(x) < 12:
            return "(" + " ".join(dump(e) for e in x) + ")"
        head = []; rest = []
        for e in x:
            (rest if (isinstance(e, list) or rest) else head).append(e)
        s = "(" + " ".join(dump(e) for e in head)
        for e in rest: s += "\n" + "  " * (ind + 1) + dump(e, ind + 1)
        return s + "\n" + "  " * ind + ")"
    if isinstance(x, Sym): return str(x)
    if isinstance(x, (int, float)): return f"{x:g}" if isinstance(x, float) else str(x)
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"') + '"'


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key); return r[0] if r else None


def library(path):
    """name -> symbol node for every top-level symbol in a .kicad_sym file."""
    root = parse(open(path, encoding="utf-8").read())[0]
    return {e[1]: e for e in find(root, "symbol")}
