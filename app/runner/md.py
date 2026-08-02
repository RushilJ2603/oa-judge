"""Tiny dependency-free Markdown -> HTML renderer.

Scope: exactly what problem statements and editorials use — headings, paragraphs, fenced and inline
code, bold/italic, unordered/ordered lists, pipe tables, blockquotes, horizontal rules. Not a full
CommonMark implementation; deliberately small so the app needs no pip installs.
"""
import html
import re

# --- Inline LaTeX math. Authored statements wrap constraints in \(...\); live model output uses
# $...$. Both are handled. This tiny renderer has no KaTeX; converting to Unicode + <sup>/<sub> keeps
# it dependency-free and renders everywhere. Only the inside of a math span is touched, and `code
# spans` are lifted out before any rule runs, so prose and code are never rewritten. ---
# A LaTeX command name is letters only, so it always ends at the first non-letter. That single fact
# is why this is ONE lookup pass over `\name` rather than a list of patterns: per-command \b anchors
# get it wrong exactly where it matters ("\sum_{i=1}" — \b fails because _ is a word character, so
# the sigma silently never appeared), and prefix pairs like \in/\infty become ordering-sensitive.
# Unknown commands fall through to their bare name, which is right for \log, \min, \max, \gcd.
_MATH_SYMBOLS = {
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "times": "×", "cdot": "·", "pm": "±", "bmod": " mod ", "div": "÷", "ast": "*",
    "ldots": "…", "dots": "…", "cdots": "…", "vdots": "⋮",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "iff": "⇔", "implies": "⇒",
    "infty": "∞", "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "approx": "≈", "equiv": "≡", "sim": "∼", "simeq": "≃", "propto": "∝", "ll": "≪", "gg": "≫",
    "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "setminus": "∖", "emptyset": "∅", "varnothing": "∅",
    "sum": "Σ", "prod": "Π", "int": "∫", "oplus": "⊕", "otimes": "⊗",
    "forall": "∀", "exists": "∃", "land": "∧", "lor": "∨", "wedge": "∧", "vee": "∨",
    "lnot": "¬", "neg": "¬", "mid": "|", "colon": ":", "cong": "≅",
    # Greek, and the complexity classes an interviewer reaches for constantly.
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ",
    "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
# Pure layout: carries nothing once the formula is flattened to text, and the bare-name fallback
# would otherwise print the word "left" in the middle of an expression.
_MATH_DROP = {"left", "right", "displaystyle", "limits", "nolimits", "big", "Big", "bigg", "Bigg",
              "bigl", "bigr", "Bigl", "Bigr", "quad", "qquad", "nonumber", "textstyle"}
# Wrappers whose only job is a font. Unwrapped to their contents: \text{RT} -> RT.
_MATH_WRAP = re.compile(
    r"\\(?:text|textit|texttt|textbf|textrm|mathrm|mathbb|mathcal|mathbf|mathit|mathsf|"
    r"mathbin|mathop|operatorname)\{([^{}]*)\}")
_MATH_CMD = re.compile(r"\\([A-Za-z]+)")
# Backslash-escaped literals must survive every later rule: \_ must not become a subscript, and
# \{ \} must not be eaten by the final brace strip. (latex, placeholder, what it renders as)
_MATH_ESCAPES = (
    (r"\_", "\x00u\x00", "_"), (r"\{", "\x00[\x00", "{"), (r"\}", "\x00]\x00", "}"),
    (r"\%", "\x00p\x00", "%"), (r"\$", "\x00m\x00", "$"), (r"\#", "\x00h\x00", "#"),
    # The input is already HTML-escaped, so a literal ampersand is "&amp;" by the time it lands.
    ("\\&amp;", "\x00a\x00", "&amp;"),
)


def _operand(x: str) -> str:
    """Parenthesise a fraction/root operand only when it needs it: 1/2, not (1)/(2)."""
    x = x or ""
    return x if re.fullmatch(r"[\w.]*", x) else f"({x})"


def _cmd(m) -> str:
    name = m.group(1)
    if name in _MATH_DROP:
        return ""
    return _MATH_SYMBOLS.get(name, name)


def _math_inner(s: str) -> str:
    for lit, slot, _out in _MATH_ESCAPES:
        s = s.replace(lit, slot)
    for _ in range(2):                                    # \mathrm{\text{x}} nests one deep
        s = _MATH_WRAP.sub(r"\1", s)
    # Before the generic pass, which would eat the command names these two need.
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}",
               lambda m: f"{_operand(m.group(1))}/{_operand(m.group(2))}", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", lambda m: "√" + _operand(m.group(1)), s)
    s = _MATH_CMD.sub(_cmd, s)
    s = re.sub(r"\^\{([^{}]*)\}", r"<sup>\1</sup>", s)   # 10^{18} -> 10<sup>18</sup>
    s = re.sub(r"\^(-?[\w])", r"<sup>\1</sup>", s)        # 10^5 -> 10<sup>5</sup>
    s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)     # A_{k} -> A<sub>k</sub>
    s = re.sub(r"_([\w])", r"<sub>\1</sub>", s)           # X_s -> X<sub>s</sub>
    s = re.sub(r"\\[,;:!\s]", " ", s)                     # thin/med spaces
    s = s.replace("{", "").replace("}", "")
    for _lit, slot, out in _MATH_ESCAPES:
        s = s.replace(slot, out)
    return s


# Dollar-delimited math is what *live model output* uses: the interviewer writes things like
# "Response Time and Waiting Time are identical ($\text{RT} = \text{WT}$)" mid-sentence. Authored
# statements can be rewritten to \(...\) offline; a model's reply cannot, so this must be handled
# here or it reaches the reader as raw LaTeX.
#
# The boundaries are deliberately strict so prose about money never becomes math: the opening $ must
# be followed by a non-space, and the closing $ must be preceded by a non-space AND not followed by a
# word character. "it costs $5 and $10 more" therefore has no valid closer and is left alone.
_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
_INLINE_RE = re.compile(r"(?<![\w$])\$(?!\s)([^$\n]*?)(?<!\s)\$(?![\w$])")
_CODE_RE = re.compile(r"`([^`]+)`")
_CODE_SLOT = "\x00c%d\x00"          # placeholder; \x00 cannot appear in HTML-escaped input
_DOLLAR_SLOT = "\x00d\x00"          # a backslash-escaped \$ — literal currency, never a delimiter


def _span(m) -> str:
    return f'<span class="math">{_math_inner(m.group(1))}</span>'


def _mathify(escaped: str) -> str:
    escaped = re.sub(r"\\\((.+?)\\\)", _span, escaped, flags=re.S)
    escaped = re.sub(r"\\\[(.+?)\\\]", _span, escaped, flags=re.S)
    escaped = _DISPLAY_RE.sub(_span, escaped)      # $$…$$ before $…$, or the outer pair splits
    escaped = _INLINE_RE.sub(_span, escaped)
    return escaped


def _inline(text: str) -> str:
    # Escape first, then re-introduce the small set of inline constructs.
    out = html.escape(text)
    out = out.replace("\\$", _DOLLAR_SLOT)
    # Pull `code spans` out BEFORE any other rule runs. Their contents are literal: `$5`, `\(x\)`
    # and `**p` are code, not markup, and must survive math/bold/link rewriting untouched.
    spans: list[str] = []

    def _stash(m):
        spans.append(m.group(1))
        return _CODE_SLOT % (len(spans) - 1)

    out = _CODE_RE.sub(_stash, out)
    # LaTeX math -> Unicode/sup/sub
    out = _mathify(out)
    # bold: **...**
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    # italic: *...*  (avoid matching bold leftovers)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)
    # links: [text](url)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                 r'<a href="\2" target="_blank" rel="noopener">\1</a>', out)
    for i, c in enumerate(spans):
        out = out.replace(_CODE_SLOT % i, f"<code>{c}</code>")
    return out.replace(_DOLLAR_SLOT, "$")


def _table(rows: list[str]) -> str:
    def cells(line):
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        return parts
    header = cells(rows[0])
    body = rows[2:]  # rows[1] is the --- separator
    h = "".join(f"<th>{_inline(c)}</th>" for c in header)
    trs = []
    for r in body:
        tds = "".join(f"<td>{_inline(c)}</td>" for c in cells(r))
        trs.append(f"<tr>{tds}</tr>")
    return f'<table><thead><tr>{h}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def render(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            out.append(f"<pre><code>{html.escape(chr(10).join(buf))}</code></pre>")
            continue

        # table: a header line followed by a |---|--- separator
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            tbl = [line, lines[i + 1]]
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                tbl.append(lines[i])
                i += 1
            out.append(_table(tbl))
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r"^\s*---+\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # blockquote
        if line.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
            continue

        # unordered list
        if re.match(r"^\s*[-*+]\s+", line):
            buf = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]))
                i += 1
            items = "".join(f"<li>{_inline(x)}</li>" for x in buf)
            out.append(f"<ul>{items}</ul>")
            continue

        # ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            buf = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            items = "".join(f"<li>{_inline(x)}</li>" for x in buf)
            out.append(f"<ol>{items}</ol>")
            continue

        # blank line
        if line.strip() == "":
            i += 1
            continue

        # paragraph: gather consecutive non-blank, non-structural lines
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|```|---+\s*$)", lines[i]) \
                and "|" not in lines[i]:
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")

    return "\n".join(out)
