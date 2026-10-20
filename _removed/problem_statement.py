"""
problem_statement.py

Generates a publication-ready "Geometric Problem Statement" box:

    Title                         -- Geometric Problem Statement
    Given Conditions / Setup      -- plain-language description of the
                                      triangle, points, and segments involved
    Definitions of Parameters     -- a clean notation list (r, r_2, r_3,
                                      u, v, m, n, ...) with LaTeX symbols
    Proof Goal                    -- the identity to be proved, boxed
    Metadata                      -- date + author

Two renderers are provided:

    render_latex(...)       -> returns a standalone .tex document string
                                (compile with pdflatex / latexmk for a
                                crisp, journal-quality PDF)
    render_matplotlib(...)  -> renders the same content directly to a PNG
                                using only matplotlib (no LaTeX toolchain
                                required)

Both renderers accept the SAME data structure, `ProblemStatement`, so you
build the content once and choose whichever output you need.

This module is intentionally independent of Flask/app.py: it can be run
standalone (see `if __name__ == "__main__"` at the bottom) or imported
and fed real values computed by solver.py / shapes.py / triangle_theorems.py
elsewhere in this project.

Error/response conventions mirror the rest of the project: a
ProblemStatementError carries a code/message/details and to_payload()
gives the usual status/error_code JSON shape.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple


class ProblemStatementError(Exception):
    """Raised for any recoverable domain error (bad/missing content)."""

    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Parameter:
    """One row in the 'Definitions of Parameters' list."""
    symbol: str          # LaTeX form, e.g. "r_2" or "u"
    meaning: str         # plain-language meaning, e.g. "inradius of triangle ABP"


@dataclass
class ProblemStatement:
    title: str = "Geometric Problem Statement"
    given: List[str] = field(default_factory=list)          # bullet points (LaTeX math allowed)
    parameters: List[Parameter] = field(default_factory=list)
    proof_goal: str = ""                                     # a single LaTeX equation, no $ needed
    author: str = "Author Name"
    date_str: Optional[str] = None                           # defaults to today

    def validate(self) -> None:
        if not self.given:
            raise ProblemStatementError(
                "MISSING_VALUE", "Provide at least one 'given' condition."
            )
        if not self.parameters:
            raise ProblemStatementError(
                "MISSING_VALUE", "Provide at least one parameter definition."
            )
        if not self.proof_goal.strip():
            raise ProblemStatementError(
                "MISSING_VALUE", "Provide a non-empty proof goal identity."
            )

    def resolved_date(self) -> str:
        return self.date_str or date.today().strftime("%B %d, %Y")


# ---------------------------------------------------------------------------
# Helpers: build a ProblemStatement from this project's own solver output
# ---------------------------------------------------------------------------

def from_cevian_split(
    m: float,
    n: float,
    r: float,
    r2: float,
    r3: float,
    u: float,
    author: str = "Author Name",
) -> ProblemStatement:
    """
    Build the classic "cevian splits a triangle into two, compare inradii"
    problem statement, using real numbers already computed elsewhere in
    this project (e.g. via solver.py: derive s, Delta, r for triangle ABC,
    then again for sub-triangles ABP and ACP once P is fixed).

    m = BP, n = PC, u = AP (the cevian), r = inradius of ABC,
    r2 = inradius of ABP, r3 = inradius of ACP.
    """
    for name, val in (("m", m), ("n", n), ("r", r), ("r2", r2), ("r3", r3), ("u", u)):
        if val is None:
            raise ProblemStatementError("MISSING_VALUE", f"Missing required value: '{name}'.")

    given = [
        r"Let $ABC$ be a triangle with incircle of radius $r$.",
        r"Let $P$ be a point on side $BC$ such that $BP = m = " + f"{m:.4g}" + r"$ and $PC = n = " + f"{n:.4g}" + r"$.",
        r"Let $AP = u = " + f"{u:.4g}" + r"$ be the cevian from $A$ to $P$.",
        r"The cevian $AP$ splits $\triangle ABC$ into $\triangle ABP$ and $\triangle ACP$, "
        r"with inradii $r_2 = " + f"{r2:.4g}" + r"$ and $r_3 = " + f"{r3:.4g}" + r"$ respectively.",
    ]

    parameters = [
        Parameter("r", "inradius of the full triangle ABC"),
        Parameter("r_2", "inradius of sub-triangle ABP"),
        Parameter("r_3", "inradius of sub-triangle ACP"),
        Parameter("u", "length of cevian AP"),
        Parameter("m", "length of segment BP"),
        Parameter("n", "length of segment PC"),
    ]

    proof_goal = (
        r"\frac{1}{r_2} + \frac{1}{r_3} \;=\; \frac{2}{r} + \frac{u(m+n)}{m\,n\,r}"
    )

    return ProblemStatement(
        given=given,
        parameters=parameters,
        proof_goal=proof_goal,
        author=author,
    )


def from_triangle_solution(
    solved: Dict[str, Any],
    proof_goal: str,
    extra_given: Optional[List[str]] = None,
    extra_parameters: Optional[List[Parameter]] = None,
    author: str = "Author Name",
) -> ProblemStatement:
    """
    Build a ProblemStatement directly from the dict returned by
    solver.solve(...) -- reusing its 'given' and 'notation' sections so
    the problem statement always matches what was actually supplied /
    derived, instead of being retyped by hand.
    """
    if solved.get("status") != "ok":
        raise ProblemStatementError(
            "INVALID_SOLUTION",
            "Expected a successful solver.solve(...) payload (status == 'ok').",
            details={"received_status": solved.get("status")},
        )

    given: List[str] = []
    for name, info in solved.get("given", {}).items():
        val = info["value"]
        meaning = info["meaning"]
        unit = "^\\circ" if "degree" in meaning else ""
        given.append(rf"${name}$ ({meaning}) is given as ${val:.4g}{unit}$.")
    given.extend(extra_given or [])

    parameters = [
        Parameter(name, meaning) for name, meaning in solved.get("notation", {}).items()
    ]
    parameters.extend(extra_parameters or [])

    return ProblemStatement(
        given=given,
        parameters=parameters,
        proof_goal=proof_goal,
        author=author,
    )


# ---------------------------------------------------------------------------
# LaTeX renderer
# ---------------------------------------------------------------------------

_LATEX_TEMPLATE = r"""\documentclass[11pt]{{article}}
\usepackage[margin=1in]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage[most]{{tcolorbox}}
\usepackage{{xcolor}}

\definecolor{{boxframe}}{{RGB}}{{30,60,110}}
\definecolor{{boxbg}}{{RGB}}{{248,249,252}}
\definecolor{{headbg}}{{RGB}}{{30,60,110}}

\newtcolorbox{{geomproblem}}[1][]{{
    enhanced,
    colback=boxbg,
    colframe=boxframe,
    colbacktitle=headbg,
    coltitle=white,
    fonttitle=\bfseries\large,
    title={title},
    boxrule=1pt,
    arc=2mm,
    top=3mm, bottom=3mm, left=4mm, right=4mm,
    #1
}}

\begin{{document}}
\thispagestyle{{empty}}

\begin{{geomproblem}}

\textbf{{Given Conditions / Setup}}
\begin{{itemize}}
{given_items}
\end{{itemize}}

\vspace{{2mm}}
\textbf{{Definitions of Parameters}}
\begin{{align*}}
{parameter_lines}
\end{{align*}}

\vspace{{2mm}}
\textbf{{Proof Goal}}
\begin{{center}}
\fbox{{$\displaystyle {proof_goal}$}}
\end{{center}}

\vspace{{3mm}}
\hfill\textit{{\small Date: {date_str} \quad | \quad Author: {author}}}

\end{{geomproblem}}

\end{{document}}
"""


def render_latex(ps: ProblemStatement) -> str:
    ps.validate()

    given_items = "\n".join(rf"    \item {line}" for line in ps.given)
    parameter_lines = " \\\\\n".join(
        rf"    {p.symbol} &= \text{{{p.meaning}}}" for p in ps.parameters
    )

    return _LATEX_TEMPLATE.format(
        title=ps.title,
        given_items=given_items,
        parameter_lines=parameter_lines,
        proof_goal=ps.proof_goal,
        date_str=ps.resolved_date(),
        author=ps.author,
    )


def save_latex(ps: ProblemStatement, path: str) -> str:
    """Write the .tex source to disk and return the path."""
    tex = render_latex(ps)
    with open(path, "w", encoding="utf-8") as f:
        f.write(tex)
    return path


# ---------------------------------------------------------------------------
# Matplotlib renderer (no LaTeX toolchain required)
# ---------------------------------------------------------------------------

def render_matplotlib(ps: ProblemStatement, out_path: str, dpi: int = 300) -> str:
    """
    Render the same problem statement as a PNG using only matplotlib +
    its built-in mathtext (a small subset of LaTeX math syntax -- no
    \\text{} or \\displaystyle, so goal/parameter strings are lightly
    adapted below). Returns out_path.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
    except ImportError as exc:
        raise ProblemStatementError(
            "MISSING_DEPENDENCY", f"matplotlib is required for render_matplotlib: {exc}"
        )

    ps.validate()

    n_given = len(ps.given)
    n_params = len(ps.parameters)
    # Rough height budget so the box grows with content instead of clipping.
    height = 4.5 + 0.42 * n_given + 0.38 * n_params
    fig, ax = plt.subplots(figsize=(8.5, height))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, height)

    outer = patches.FancyBboxPatch(
        (0.3, 0.3), 9.4, height - 0.6,
        boxstyle="round,pad=0.05,rounding_size=0.15",
        linewidth=1.5, edgecolor="#1e3c6e", facecolor="#f8f9fc",
    )
    ax.add_patch(outer)

    title_h = 0.9
    title_y0 = height - 0.3 - title_h
    title_box = patches.FancyBboxPatch(
        (0.3, title_y0), 9.4, title_h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        linewidth=0, facecolor="#1e3c6e",
    )
    ax.add_patch(title_box)
    ax.text(5, title_y0 + title_h / 2, ps.title,
            fontsize=16, fontweight="bold", color="white",
            ha="center", va="center")

    y = title_y0 - 0.35

    def section_header(y: float, text: str) -> float:
        ax.text(0.6, y, text, fontsize=12, fontweight="bold", color="#1e3c6e")
        return y - 0.42

    def bullet(y: float, text: str) -> float:
        ax.text(0.8, y, f"\u2022  {text}", fontsize=10.2, va="top")
        return y - 0.4

    y = section_header(y, "Given Conditions / Setup")
    for line in ps.given:
        y = bullet(y, line)

    y -= 0.12
    y = section_header(y, "Definitions of Parameters")
    for p in ps.parameters:
        ax.text(0.8, y, f"${p.symbol}$  =  {p.meaning}", fontsize=10.2, va="top")
        y -= 0.38

    y -= 0.15
    y = section_header(y, "Proof Goal")
    goal_box = patches.FancyBboxPatch(
        (1.0, y - 0.85), 8, 0.75,
        boxstyle="round,pad=0.05", linewidth=1.2,
        edgecolor="#1e3c6e", facecolor="white",
    )
    ax.add_patch(goal_box)
    ax.text(5, y - 0.48, f"${ps.proof_goal}$", fontsize=13, ha="center", va="center")

    ax.text(9.1, 0.55, f"Date: {ps.resolved_date()}  |  Author: {ps.author}",
            fontsize=9, ha="right", style="italic", color="#333333")

    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))

    # Example: cevian-split problem with concrete numbers.
    ps = from_cevian_split(m=4.0, n=3.0, r=1.2, r2=0.9, r3=0.8, u=5.0,
                            author="Hasin Khan")

    tex_path = save_latex(ps, os.path.join(here, "problem_statement.tex"))
    print(f"LaTeX source written to: {tex_path}")

    try:
        png_path = render_matplotlib(ps, os.path.join(here, "problem_statement.png"))
        print(f"PNG rendered to: {png_path}")
    except ProblemStatementError as exc:
        print(f"Skipped PNG render: {exc.message}")
