"""
etc_position.py

Find WHERE any Kimberling center X(n) sits on a concrete triangle, so the
Encyclopedia page can draw it. Works for every center whose position can be
worked out, not just the small verified database:

  1. verified     - the hand-checked formulas in triangle_centers.db
  2. etc_formula  - the Barycentrics / Trilinears published on the ETC page
                    (read from the local .etc_cache, or fetched once)
  3. construction - names such as "X(100)X(516)∩X(241)X(514)", midpoints,
                    reflections, isogonal/isotomic conjugates, complements
                    (their operands are located recursively)

ETC formulas are written for people, not computers: implicit multiplication
("bc[(a - b) cot C + ...]"), "tan A/2", <sup>/<sub> tags, S_A, the short form
"f(a,b,c) : :" meaning "cyclic permutations of f", "where f(a,b,c) = ...",
and "x : y : z = X(n)". This module has its own tokenizer + recursive-descent
parser for that notation and evaluates the resulting tree directly. Nothing
from the web is ever passed to eval().

ETC pages occasionally contain typos, and a notation we misread would give a
wrong point without any error. So every formula line is evaluated, the lines
are grouped by the point they give, and each group is checked against the
"X(n) lies on these lines: {i, j}, ..." list printed on the same ETC entry.
The group that agrees with those lines wins.

Public entry point:
    locate_center(kimberling_id, Triangle) -> dict   (never raises)
"""

import html
import math
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import etc_lookup
from centers import Triangle, TriangleCenterError, compute_center

MAX_CONSTRUCTION_DEPTH = 4
MAX_LINE_CHECKS = 6


class _Unsupported(Exception):
    """The formula uses notation this parser does not understand."""


class _Undefined(Exception):
    """The formula is understood but undefined for this triangle."""


# ---------------------------------------------------------------------------
# 1. ETC text -> plain math text
# ---------------------------------------------------------------------------

def _clean_inline(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _html_to_math(s: str) -> str:
    s = re.sub(r"<sup>(.*?)</sup>", r"^(\1)", s, flags=re.S | re.I)
    s = re.sub(r"<sub>(.*?)</sub>", r"_\1 ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    for old, new in (
        ("\u2212", "-"), ("\u2013", "-"), ("\u00d7", "*"), ("\u00b7", "*"),
        ("\u22c5", "*"), ("\u221a", "sqrt"), ("\u03c0", "pi"),
        ("\u00b2", "^2"), ("\u00b3", "^3"),
    ):
        s = s.replace(old, new)
    return s.strip()


_BIND_RE = re.compile(
    r"([xyzuvw])\s*:\s*([xyzuvw])\s*:\s*([xyzuvw])\s*=\s*X\((\d+)\)"
)
_DEF_RE = re.compile(
    r"^\s*([A-Za-z])\(\s*[A-Za-z]\s*,\s*[A-Za-z]\s*,\s*[A-Za-z]\s*\)\s*=\s*(.+?)[\s.]*$"
)


def _prepare(text: str):
    """Split one ETC line into (main formula, {fname: body}, binding).

    binding is ((n1, n2, n3), k) for "x : y : z = X(k)", else None."""
    s = re.sub(r"\s+", " ", _html_to_math(text)).strip()
    # trailing credits such as "(M. Iliev, 5/13/07)" or "(see below)"
    s = re.sub(r"\s*\((?:[^()]*\d{1,2}/\d{1,2}/\d{2,4}[^()]*|see [^()]*)\)\s*$", "", s)

    binding = None
    m = _BIND_RE.search(s)
    if m:
        binding = ((m.group(1), m.group(2), m.group(3)), int(m.group(4)))
        s = s[:m.start()] + s[m.end():]
        s = re.sub(r"[,\s]*(?:where)?[\s,.]*$", "", s)

    defs: Dict[str, str] = {}
    m = re.search(r",?\s*\bwhere\b", s)
    if m:
        main, defs_text = s[:m.start()], s[m.end():]
        if defs_text.strip():
            dm = _DEF_RE.match(defs_text)
            if not dm:
                raise _Unsupported("unreadable 'where' clause")
            defs[dm.group(1)] = dm.group(2)
    else:
        main = s
    return main.strip(), defs, binding


# ---------------------------------------------------------------------------
# 2. Tokenizer
# ---------------------------------------------------------------------------

_FUNCS = ("sqrt", "Sqrt", "sqr", "sin", "cos", "tan", "cot", "sec", "csc")
_FUNC_ALIAS = {"Sqrt": "sqrt", "sqr": "sqrt"}
_VARS = set("abcABCSRrs\u03c9")
_SUBBED = {"S_A", "S_B", "S_C", "S_\u03c9"}
_OPS = set("+-*/^()[]{}:,")
_TOKEN_RE = re.compile(
    r"\s*(?:(\d+(?:\.\d+)?)|([A-Za-z\u03c9]+(?:_[A-Za-z0-9\u03c9]+)?)|(.))"
)


def _expand_ident(ident: str, tokens: list, ufuncs: set, extra_vars: set) -> None:
    sub = None
    if "_" in ident:
        ident, sub = ident.split("_", 1)
    i = 0
    while i < len(ident):
        if ident.startswith("area", i):
            tokens.append(("var", "area"))
            i += 4
            continue
        func = next((f for f in _FUNCS if ident.startswith(f, i)), None)
        if func:
            tokens.append(("func", _FUNC_ALIAS.get(func, func)))
            i += len(func)
            continue
        if ident.startswith("pi", i):
            tokens.append(("num", math.pi))
            i += 2
            continue
        ch = ident[i]
        i += 1
        if ch in ufuncs:
            tokens.append(("ufunc", ch))
            continue
        if ch in extra_vars:
            tokens.append(("var", ch))
            continue
        name = ch
        if ch == "S" and sub is None and i < len(ident) and ident[i] in "ABC\u03c9":
            # Conway notation written inline: SA, SB, SC, S\u03c9 (= S_A, ...)
            name = "S_" + ident[i]
            i += 1
        elif sub is not None and i == len(ident):
            name = ch + "_" + sub
            if name not in _SUBBED:
                raise _Unsupported(f"unknown symbol {name!r}")
        elif ch not in _VARS:
            raise _Unsupported(f"unknown symbol {ch!r}")
        tokens.append(("var", name))


def _tokenize(text: str, ufuncs: set = frozenset(), extra_vars: set = frozenset()) -> list:
    tokens: list = []
    for m in _TOKEN_RE.finditer(text):
        num, ident, other = m.groups()
        if num is not None:
            tokens.append(("num", float(num)))
        elif ident is not None:
            _expand_ident(ident, tokens, set(ufuncs), set(extra_vars))
        elif other in _OPS:
            tokens.append(("op", other))
        else:
            raise _Unsupported(f"unexpected character {other!r}")
    return tokens


# ---------------------------------------------------------------------------
# 3. Parser (implicit multiplication, brackets, "cos A", "tan A/2", f(a,b,c))
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, tokens: list):
        self.t = tokens
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def at_op(self, ch: str) -> bool:
        p = self.peek()
        return p is not None and p[0] == "op" and p[1] == ch

    def starts_atom(self) -> bool:
        p = self.peek()
        if p is None:
            return False
        return p[0] in ("num", "var", "func", "ufunc") or (p[0] == "op" and p[1] in "([{")

    def whole_expr(self):
        node = self.expr()
        if self.peek() is not None:
            raise _Unsupported("unexpected trailing text")
        return node

    def formula(self) -> list:
        parts = [self.expr()]
        while self.at_op(":"):
            self.i += 1
            p = self.peek()
            if p is None or (p[0] == "op" and p[1] == ":"):
                parts.append(None)
            else:
                parts.append(self.expr())
        if self.peek() is not None:
            raise _Unsupported("unexpected trailing text")
        return parts

    def expr(self):
        node = self.term()
        while True:
            if self.at_op("+"):
                self.i += 1
                node = ("add", node, self.term())
            elif self.at_op("-"):
                self.i += 1
                node = ("sub", node, self.term())
            else:
                return node

    def term(self):
        node = self.unary()
        while True:
            if self.at_op("*"):
                self.i += 1
                node = ("mul", node, self.unary())
            elif self.at_op("/"):
                self.i += 1
                node = ("div", node, self.unary())
            elif self.starts_atom():
                node = ("mul", node, self.power())  # implicit multiplication
            else:
                return node

    def unary(self):
        if self.at_op("-"):
            self.i += 1
            return ("neg", self.unary())
        if self.at_op("+"):
            self.i += 1
            return self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.at_op("^"):
            self.i += 1
            return ("pow", base, self.exponent())
        return base

    def exponent(self):
        if self.at_op("-"):
            self.i += 1
            return ("neg", self.exponent())
        if self.at_op("+"):
            self.i += 1
            return self.exponent()
        return self.power()

    def atom(self):
        p = self.peek()
        if p is None:
            raise _Unsupported("unexpected end of formula")
        self.i += 1
        kind, val = p
        if kind == "num":
            return ("num", val)
        if kind == "var":
            return ("var", val)
        if kind == "func":
            return self.func_call(val)
        if kind == "ufunc":
            if not self.at_op("("):
                raise _Unsupported("function name without arguments")
            self.i += 1
            args = [self.expr()]
            while self.at_op(","):
                self.i += 1
                args.append(self.expr())
            if not self.at_op(")"):
                raise _Unsupported("unbalanced brackets")
            self.i += 1
            return ("call", val, args)
        if kind == "op" and val in "([{":
            close = {"(": ")", "[": "]", "{": "}"}[val]
            node = self.expr()
            if not self.at_op(close):
                raise _Unsupported("unbalanced brackets")
            self.i += 1
            return node
        raise _Unsupported(f"unexpected token {val!r}")

    def func_call(self, name: str):
        power = None
        if self.at_op("^"):  # sin^2 A
            self.i += 1
            power = self.exponent()
        if self.at_op("(") or self.at_op("[") or self.at_op("{"):
            arg = self.atom()
        else:
            arg = self.bare_arg()
        node = ("fn", name, arg)
        return ("pow", node, power) if power is not None else node

    def bare_arg(self):
        """Argument without brackets: 'cos A', 'sin 2A', 'tan A/2'."""
        coeff = None
        p = self.peek()
        if p and p[0] == "num":
            self.i += 1
            coeff = ("num", p[1])
        p = self.peek()
        if p and p[0] == "var":
            self.i += 1
            arg = ("var", p[1])
            if coeff is not None:
                arg = ("mul", coeff, arg)
        elif coeff is not None:
            arg = coeff
        else:
            raise _Unsupported("function without an argument")
        if self.at_op("/"):
            nxt = self.t[self.i + 1] if self.i + 1 < len(self.t) else None
            if nxt and nxt[0] == "num":
                self.i += 2
                arg = ("div", arg, ("num", nxt[1]))
        return arg


# ---------------------------------------------------------------------------
# 4. Evaluation
# ---------------------------------------------------------------------------

_CYCLE = {"a": "b", "b": "c", "c": "a", "A": "B", "B": "C", "C": "A",
          "S_A": "S_B", "S_B": "S_C", "S_C": "S_A"}


def _shifted_env(env: Dict[str, float], times: int, cycle: Dict[str, str]) -> Dict[str, float]:
    """Environment for f(b,c,a) (times=1) or f(c,a,b) (times=2)."""
    out = dict(env)
    for name in cycle:
        src = name
        for _ in range(times):
            src = cycle[src]
        out[name] = env[src]
    return out


def _arg_shift(args: list, ctx: dict) -> int:
    """For f(b,c,a)-style calls: how many cyclic steps the arguments are."""
    if len(args) != 3 or not all(a[0] == "var" for a in args):
        raise _Unsupported("function called with non-variable arguments")
    names = tuple(a[1] for a in args)
    for group in ctx["groups"]:
        for k in range(3):
            if names == group[k:] + group[:k]:
                return k
    raise _Unsupported("function called with unusual arguments")


def _ev(node, env, ctx):
    k = node[0]
    if k == "num":
        return node[1]
    if k == "var":
        return env[node[1]]
    if k == "neg":
        return -_ev(node[1], env, ctx)
    if k == "call":
        body = ctx["defs"][node[1]]
        shift = _arg_shift(node[2], ctx)
        return _ev(body, _shifted_env(env, shift, ctx["cycle"]), ctx)
    if k == "fn":
        x = _ev(node[2], env, ctx)
        f = node[1]
        if f == "sin":
            return math.sin(x)
        if f == "cos":
            return math.cos(x)
        if f == "tan":
            return math.tan(x)
        if f == "cot":
            return 1.0 / math.tan(x)
        if f == "sec":
            return 1.0 / math.cos(x)
        if f == "csc":
            return 1.0 / math.sin(x)
        if f == "sqrt":
            return math.sqrt(x)
        raise _Unsupported(f"function {f}")
    left, right = _ev(node[1], env, ctx), _ev(node[2], env, ctx)
    if k == "add":
        return left + right
    if k == "sub":
        return left - right
    if k == "mul":
        return left * right
    if k == "div":
        return left / right
    if k == "pow":
        value = left ** right
        if isinstance(value, complex):
            raise _Undefined("complex result")
        return value
    raise _Unsupported(k)


def _triangle_env(tri: Triangle) -> Dict[str, float]:
    a, b, c = tri.side_lengths()

    def angle(x, y, z):  # angle opposite side x
        return math.acos(max(-1.0, min(1.0, (y * y + z * z - x * x) / (2 * y * z))))

    A, B = angle(a, b, c), angle(b, c, a)
    C = math.pi - A - B
    S = abs(tri.area2())  # ETC's S = 2 * area
    s = (a + b + c) / 2
    sq = a * a + b * b + c * c
    return {
        "a": a, "b": b, "c": c, "A": A, "B": B, "C": C,
        "S": S, "area": S / 2, "s": s, "R": a * b * c / (2 * S), "r": S / (2 * s),
        "S_A": (b * b + c * c - a * a) / 2,
        "S_B": (c * c + a * a - b * b) / 2,
        "S_C": (a * a + b * b - c * c) / 2,
        "S_\u03c9": sq / 2,
        "\u03c9": math.atan2(2 * S, sq),
    }


def _weights_from_text(kind: str, text: str, env: Dict[str, float], coord_source=None):
    """Barycentric weights from one ETC formula line (raises _Unsupported /
    _Undefined when the line cannot be used)."""
    main, defs, binding = _prepare(text)
    env = dict(env)
    cycle = dict(_CYCLE)
    groups = [("a", "b", "c"), ("A", "B", "C")]
    extra: set = set()
    if binding:
        names, n = binding
        if coord_source is None:
            raise _Undefined("needs the coordinates of another center")
        env.update(zip(names, coord_source(n, kind)))
        cycle.update({names[0]: names[1], names[1]: names[2], names[2]: names[0]})
        groups.append(names)
        extra = set(names)

    parts = _Parser(_tokenize(main, set(defs), extra)).formula()
    if len(parts) != 3:
        raise _Unsupported("not a 3-part formula")
    bodies = {name: _Parser(_tokenize(body, set(), extra)).whole_expr()
              for name, body in defs.items()}
    ctx = {"defs": bodies, "cycle": cycle, "groups": groups}

    try:
        if parts[1] is None and parts[2] is None:  # "f : :" -> cyclic shifts
            w = (_ev(parts[0], env, ctx),
                 _ev(parts[0], _shifted_env(env, 1, cycle), ctx),
                 _ev(parts[0], _shifted_env(env, 2, cycle), ctx))
        elif all(p is not None for p in parts):
            w = tuple(_ev(p, env, ctx) for p in parts)
        else:
            raise _Unsupported("mixed formula")
    except (ZeroDivisionError, OverflowError, ValueError) as exc:
        raise _Undefined(str(exc))
    if kind == "tri":  # trilinears -> barycentrics
        w = (w[0] * env["a"], w[1] * env["b"], w[2] * env["c"])
    if not all(math.isfinite(v) for v in w):
        raise _Undefined("non-finite weights")
    return w


# ---------------------------------------------------------------------------
# 5. Reading a center's entry from the ETC page
# ---------------------------------------------------------------------------

@lru_cache(maxsize=512)
def _etc_block(kimberling_id: int) -> Optional[str]:
    part = etc_lookup.get_part_number(kimberling_id)
    page = etc_lookup._fetch_part_page(part, 15)
    return etc_lookup.find_center_html(page, kimberling_id)


def _etc_name(block: str) -> str:
    m = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
    text = _clean_inline(m.group(1)) if m else ""
    return re.sub(r"^X\(\d+\)\s*=\s*", "", text)


_FORMULA_KEY_RE = re.compile(r"(Barycentrics|Trilinears)(?:\s|&nbsp;)+")
# Where one published formula stops: the next formula/tripolar heading, the end
# of the paragraph, or the start of an "X(n) = ..." relationship line.
_FORMULA_END_RE = re.compile(
    r"(?:Barycentrics|Trilinears|Tripolars)(?:\s|&nbsp;)|</?p>|X\(\d+\)(?:\s|&nbsp;)*="
)


def _etc_formula_lines(block: str) -> List[Tuple[str, str]]:
    """[(kind, text), ...] in page order.

    Most entries are one line ("Barycentrics a : b : c<br>"), but ETC also
    writes "f(a,b,c) : f(b,c,a) : f(c,a,b), where<br> f(a,b,c) = ..." with the
    definition on the following lines, and some entries keep their formulas
    inside the first <p>. Everything before the first "lies on" is searched,
    and a line ending in "where" is continued up to the next heading."""
    head = block.split("</h3>", 1)[-1]
    cut = re.search(r"(?:<p>\s*)?(?:X\(\d+\)(?:\s|&nbsp;)*)?lies on", head)
    if cut:
        head = head[:cut.start()]
    found: List[Tuple[str, str]] = []
    for m in _FORMULA_KEY_RE.finditer(head):
        rest = head[m.end():]
        end = _FORMULA_END_RE.search(rest)
        long_text = rest[:end.start()] if end else rest
        short_text = re.split(r"<br\s*/?>", long_text, maxsplit=1)[0]
        needs_definition = re.search(r"\bwhere\s*$", _clean_inline(short_text))
        text = long_text if needs_definition else short_text
        if text.strip():
            found.append(("bary" if m.group(1) == "Barycentrics" else "tri", text.strip()))
    return found


# Part 1 prints the pairs bare ("lies on these lines: 2,8   3,35"), later parts
# print them in braces ("{2, 8}, {3, 35}"); the list ends at </p> or <br>.
_LINES_RE = re.compile(
    r"lies on[^<]*?\b(?:these lines|the line)\s*:?(.*?)(?:</p>|<br|$)", re.S
)


def _listed_lines(block: str) -> List[Tuple[int, int]]:
    """The (i, j) pairs from "X(n) lies on these lines: i,j  k,l ..." (either
    the bare or the braced notation)."""
    m = _LINES_RE.search(block)
    if not m:
        return []
    text = m.group(1).replace("&nbsp;", " ")
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*,\s*(\d+)", text)]


# ---------------------------------------------------------------------------
# 6. Geometry helpers + constructions from the center's name
# ---------------------------------------------------------------------------

def _dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _collinear(p, q, r) -> bool:
    d1 = (q[0] - p[0], q[1] - p[1])
    d2 = (r[0] - p[0], r[1] - p[1])
    scale = math.hypot(*d1) * math.hypot(*d2)
    if scale < 1e-12:
        return True
    return abs(d1[0] * d2[1] - d1[1] * d2[0]) / scale < 1e-6


def _barycentric(tri: Triangle, p) -> Tuple[float, float, float]:
    d = tri.area2()
    alpha = ((tri.B[0] - p[0]) * (tri.C[1] - p[1]) - (tri.C[0] - p[0]) * (tri.B[1] - p[1])) / d
    beta = ((tri.C[0] - p[0]) * (tri.A[1] - p[1]) - (tri.A[0] - p[0]) * (tri.C[1] - p[1])) / d
    return alpha, beta, 1.0 - alpha - beta


def _line_intersection(p1, p2, p3, p4):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p1, p2, p3, p4
    len1, len2 = _dist(p1, p2), _dist(p3, p4)
    if len1 < 1e-12 or len2 < 1e-12:
        raise _Undefined("a construction line is degenerate (two identical points)")
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-12 * len1 * len2:
        raise _Undefined("the two construction lines are parallel or identical")
    u = x1 * y2 - y1 * x2
    v = x3 * y4 - y3 * x4
    return ((u * (x3 - x4) - (x1 - x2) * v) / d, (u * (y3 - y4) - (y1 - y2) * v) / d)


_INTERSECT_RE = re.compile(r"^X\((\d+)\)\s*X\((\d+)\)\s*\u2229\s*X\((\d+)\)\s*X\((\d+)\)$")
_MIDPOINT_RE = re.compile(r"^midpoint of X\((\d+)\) and X\((\d+)\)$", re.I)
_REFLECT_RE = re.compile(r"^reflection of X\((\d+)\) in X\((\d+)\)$", re.I)
_UNARY_RE = re.compile(
    r"^(isogonal conjugate|isotomic conjugate|complement|anticomplement) of X\((\d+)\)$", re.I
)


# ---------------------------------------------------------------------------
# 7. Public API
# ---------------------------------------------------------------------------

def _confidence(method: str, consistency) -> str:
    """How much to trust a position.

    cross_checked - at least 2 of the lines ETC lists for this center were
                    tested and the point lies on every one of them
    hand_verified - from the local verified database, and nothing ETC lists
                    contradicts it
    unverified    - anything else: ETC lists fewer than 2 usable lines (so
                    the reading of the formula could not be double-checked),
                    only some of the lines agree, or the point was built
                    from other centers' positions
    """
    checked, passed = consistency if consistency else (0, 0)
    if checked >= 2 and passed == checked:
        return "cross_checked"
    if method == "verified" and passed == checked:
        return "hand_verified"
    return "unverified"


def _confidence_note(method: str, consistency) -> Optional[str]:
    checked, passed = consistency if consistency else (0, 0)
    if checked > 0 and passed < checked:
        return (f"Only {passed} of the {checked} lines ETC lists for this center pass "
                "through the computed point, so the position may be wrong.")
    if method == "construction":
        return ("Built from the positions of other centers, which are not "
                "individually cross-checked, so the position may be wrong.")
    return ("ETC lists fewer than 2 usable lines through this center, so the "
            "position could not be double-checked and may be wrong.")


def _ok(kid, tri, pos, method, detail, weights=None, consistency=None):
    out = {
        "status": "ok",
        "kimberling_id": kid,
        "method": method,
        "detail": detail,
        "position": {"x": pos[0], "y": pos[1]},
        "input_triangle": {"A": tri.A, "B": tri.B, "C": tri.C},
    }
    if weights is not None:
        total = sum(weights)
        if total:
            out["barycentric_weights_normalized"] = [w / total for w in weights]
    if consistency and consistency[0]:
        out["consistency"] = {"lines_checked": consistency[0], "lines_passed": consistency[1]}
    out["confidence"] = _confidence(method, consistency)
    if out["confidence"] == "unverified":
        out["confidence_note"] = _confidence_note(method, consistency)
    return out


def _err(kid, code, message):
    return {"status": "error", "error_code": code, "kimberling_id": kid, "message": message}


def locate_center(kimberling_id: int, tri: Triangle, _depth: int = 0,
                  _memo: Optional[dict] = None) -> Dict[str, Any]:
    """Return {'status': 'ok', 'position': {'x', 'y'}, 'method', ...} or an
    error payload. Never raises."""
    memo = _memo if _memo is not None else {}
    cached = memo.get(kimberling_id)
    if cached is not None:
        cached_depth, cached_result = cached
        # A success is valid at any depth. A failure may only be reused if it
        # was found with at least as much construction depth left as we have
        # now: a center that failed at depth 4 (where constructions are not
        # allowed) must be retried when asked for again at depth 1.
        if cached_result.get("status") == "ok" or cached_depth <= _depth:
            return cached_result
    try:
        result = _locate(kimberling_id, tri, _depth, memo)
    except Exception as exc:  # noqa: BLE001 - this function promises not to raise
        result = _err(kimberling_id, "POSITION_ERROR",
                      f"Unexpected problem while locating X({kimberling_id}): {exc}")
    memo[kimberling_id] = (_depth, result)
    return result


def _operand_point(i: int, tri: Triangle, depth: int, memo: dict):
    r = locate_center(i, tri, depth, memo)
    if r.get("status") != "ok":
        return None
    return (r["position"]["x"], r["position"]["y"])


def _line_checks(kid: int, point, block: Optional[str], tri: Triangle, memo: dict) -> Tuple[int, int]:
    """(checked, passed): is `point` on the lines ETC lists for X(kid)?"""
    if not block:
        return 0, 0
    checked = passed = 0
    for i, j in _listed_lines(block)[:MAX_LINE_CHECKS]:
        if kid in (i, j):
            continue
        q = _operand_point(i, tri, 1, memo)
        r = _operand_point(j, tri, 1, memo)
        if q is None or r is None or _dist(q, r) < 1e-9:
            continue
        checked += 1
        if _collinear(point, q, r):
            passed += 1
    return checked, passed


def _safe_block(kid: int):
    try:
        return _etc_block(kid), None
    except etc_lookup.EtcLookupError as exc:
        return None, _err(kid, exc.code, exc.message)


def _locate(kid: int, tri: Triangle, depth: int, memo: dict) -> Dict[str, Any]:
    try:
        tri.validate()
    except TriangleCenterError as exc:
        return exc.to_payload()
    verify = depth == 0   # cross-checking is only done for the center asked for

    # 1. Verified database
    db_fallback = None
    verified = compute_center(kid, tri)
    if verified.get("status") == "ok":
        pos = verified["cartesian_position"]
        point = (pos["x"], pos["y"])
        weights = verified.get("barycentric_weights_normalized")
        detail = "Hand-verified formula from the local database."
        if not verify:
            return _ok(kid, tri, point, "verified", detail, weights)
        block, _ = _safe_block(kid)
        checked, passed = _line_checks(kid, point, block, tri, memo)
        result = _ok(kid, tri, point, "verified", detail, weights, (checked, passed))
        if checked >= 2 and passed == 0:
            # The database formula disagrees with every line ETC lists for it.
            db_fallback = result
        else:
            return result
    elif verified.get("error_code") != "CENTER_NOT_FOUND":
        return verified

    # 2. Formulas published on the ETC page
    block, problem = _safe_block(kid)
    if problem:
        return db_fallback or problem
    if block is None:
        return db_fallback or _err(
            kid, "CENTER_NOT_FOUND_ON_PAGE",
            f"X({kid}) was not found in the Encyclopedia of Triangle Centers.")

    env = _triangle_env(tri)

    def coord_source(n, kind):
        p = _operand_point(n, tri, depth + 1, memo)
        if p is None:
            raise _Undefined(f"X({n}) could not be located")
        alpha, beta, gamma = _barycentric(tri, p)
        if kind == "bary":
            return alpha, beta, gamma
        return alpha / env["a"], beta / env["b"], gamma / env["c"]

    at_infinity = False
    candidates = []
    for kind, text in _etc_formula_lines(block):
        try:
            weights = _weights_from_text(kind, text, env, coord_source)
            point = tri.barycentric_to_cartesian(weights)
        except TriangleCenterError:  # weights sum to zero
            at_infinity = True
            continue
        except (_Unsupported, _Undefined):
            continue
        candidates.append((kind, weights, point))

    if candidates:
        # Group the lines by the point they give; keep the group that agrees
        # best with the lines ETC lists for this center.
        tol = 1e-6 * (env["a"] + env["b"] + env["c"])
        groups: List[list] = []
        for cand in candidates:
            for g in groups:
                if _dist(cand[2], g[0][2]) <= tol:
                    g.append(cand)
                    break
            else:
                groups.append([cand])
        scored = []
        for index, g in enumerate(groups):
            checked, passed = _line_checks(kid, g[0][2], block, tri, memo) if verify else (0, 0)
            scored.append((passed, len(g), -index, checked, g))
        scored.sort(key=lambda t: t[:3], reverse=True)
        passed, _, _, checked, best = scored[0]
        if not (checked >= 2 and passed == 0):
            kind, weights, point = best[0]
            label = "Barycentrics" if kind == "bary" else "Trilinears"
            return _ok(kid, tri, point, "etc_formula",
                       f"Computed from the {label} published on ETC.",
                       weights, (checked, passed))
        # every reading disagrees with ETC's own line list: do not trust it

    if db_fallback:
        return db_fallback
    if not candidates and (at_infinity or _is_at_infinity_by_page(kid, block)):
        return _err(kid, "CENTER_AT_INFINITY",
                    f"X({kid}) is a point at infinity for this triangle, so it cannot be drawn.")

    # 3. Construction named in the heading
    if depth < MAX_CONSTRUCTION_DEPTH:
        built = _locate_by_construction(kid, _etc_name(block), tri, depth, memo)
        if built is not None:
            return built

    # 4. Last resort: ETC lists lines through this center ("lies on these
    #    lines: {i, j}, {k, l}"), so it is where two of those lines cross.
    if depth < MAX_CONSTRUCTION_DEPTH:
        built = _locate_by_listed_lines(kid, block, tri, depth, memo)
        if built is not None:
            return built

    return _err(kid, "POSITION_UNAVAILABLE",
                f"Could not work out a reliable position for X({kid}): its ETC entry has no "
                "formula this program can read (or the readings disagree with ETC's own "
                "line list), and its name is not a simple construction.")


def _is_at_infinity_by_page(kid: int, block: str) -> bool:
    """True when ETC itself says X(kid) is a point at infinity.

    Some entries (e.g. X(528) "DIRECTION OF VECTOR AX + BX + CX") use a formula
    layout this parser cannot read, but the page states the answer in words:
    "X(n) lies on the line at infinity", or the name starts with "DIRECTION OF".
    Reporting these as CENTER_AT_INFINITY is correct, instead of claiming that
    the position "could not be worked out"."""
    if _etc_name(block).upper().startswith("DIRECTION OF"):
        return True
    return re.search(rf"X\({kid}\)(?:\s|&nbsp;)*lies on the line at infinity", block) is not None


def _locate_by_listed_lines(kid, block, tri, depth, memo) -> Optional[Dict[str, Any]]:
    """Intersect two of the lines ETC says pass through X(kid). When ETC lists
    more than two lines, the crossing point must lie on all of them, which
    guards against a wrongly located operand."""
    lines = []
    for i, j in _listed_lines(block):
        if kid in (i, j):
            continue
        p = _operand_point(i, tri, depth + 1, memo)
        q = _operand_point(j, tri, depth + 1, memo)
        if p is None or q is None or _dist(p, q) < 1e-9:
            continue
        lines.append((i, j, p, q))
        if len(lines) >= MAX_LINE_CHECKS + 2:
            break
    for x in range(len(lines)):
        for y in range(x + 1, len(lines)):
            i, j, p, q = lines[x]
            k, l, r, s = lines[y]
            try:
                pos = _line_intersection(p, q, r, s)
            except _Undefined:
                continue
            if not all(math.isfinite(v) for v in pos):
                continue
            others = [ln for n, ln in enumerate(lines) if n not in (x, y)]
            if all(_collinear(pos, ln[2], ln[3]) for ln in others):
                return _ok(kid, tri, pos, "construction",
                           f"Intersection of line X({i})X({j}) with line X({k})X({l}), "
                           f"both listed on ETC as passing through X({kid}).")
    return None


def _locate_by_construction(kid, name, tri, depth, memo) -> Optional[Dict[str, Any]]:
    name = name.strip().rstrip(".")

    def point(i):
        p = _operand_point(i, tri, depth + 1, memo)
        if p is None:
            raise _Undefined(f"X({i}) could not be located")
        return p

    try:
        m = _INTERSECT_RE.match(name)
        if m:
            i, j, k, l = (int(g) for g in m.groups())
            pos = _line_intersection(point(i), point(j), point(k), point(l))
            return _ok(kid, tri, pos, "construction",
                       f"Intersection of line X({i})X({j}) with line X({k})X({l}).")
        m = _MIDPOINT_RE.match(name)
        if m:
            i, j = (int(g) for g in m.groups())
            (x1, y1), (x2, y2) = point(i), point(j)
            return _ok(kid, tri, ((x1 + x2) / 2, (y1 + y2) / 2), "construction",
                       f"Midpoint of X({i}) and X({j}).")
        m = _REFLECT_RE.match(name)
        if m:
            i, j = (int(g) for g in m.groups())
            (x1, y1), (x2, y2) = point(i), point(j)
            return _ok(kid, tri, (2 * x2 - x1, 2 * y2 - y1), "construction",
                       f"Reflection of X({i}) in X({j}).")
        m = _UNARY_RE.match(name)
        if m:
            what, i = m.group(1).lower(), int(m.group(2))
            p = point(i)
            gx = (tri.A[0] + tri.B[0] + tri.C[0]) / 3
            gy = (tri.A[1] + tri.B[1] + tri.C[1]) / 3
            if what == "complement":
                pos = ((3 * gx - p[0]) / 2, (3 * gy - p[1]) / 2)
            elif what == "anticomplement":
                pos = (3 * gx - 2 * p[0], 3 * gy - 2 * p[1])
            else:
                alpha, beta, gamma = _barycentric(tri, p)
                a, b, c = tri.side_lengths()
                if min(abs(alpha), abs(beta), abs(gamma)) < 1e-12:
                    raise _Undefined(f"X({i}) lies on a side line, so its conjugate is at infinity")
                if what == "isogonal conjugate":
                    w = (a * a / alpha, b * b / beta, c * c / gamma)
                else:
                    w = (1 / alpha, 1 / beta, 1 / gamma)
                pos = tri.barycentric_to_cartesian(w)
            return _ok(kid, tri, pos, "construction", f"{what.capitalize()} of X({i}).")
    except (_Undefined, TriangleCenterError) as exc:
        return _err(kid, "POSITION_UNAVAILABLE", str(exc))
    return None
