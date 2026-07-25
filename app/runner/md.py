"""Tiny dependency-free Markdown -> HTML renderer.

Scope: exactly what problem statements and editorials use — headings, paragraphs, fenced and inline
code, bold/italic, unordered/ordered lists, pipe tables, blockquotes, horizontal rules. Not a full
CommonMark implementation; deliberately small so the app needs no pip installs.
"""
import html
import re

# --- Inline LaTeX math: authored statements (esp. Grok-generated ones) wrap constraints in \(...\)
# with commands like \le, 10^5, N_i. This tiny renderer has no KaTeX; converting to Unicode +
# <sup>/<sub> keeps it dependency-free and renders everywhere. Only the inside of \(...\)/\[...\] is
# touched, so plain prose and `code spans` (e.g. the older `2 <= n <= 10^5` style) are untouched. ---
_MATH_CMDS = [
    (r"\\leq?\b", "≤"), (r"\\geq?\b", "≥"), (r"\\neq\b", "≠"), (r"\\ne\b", "≠"),
    (r"\\times\b", "×"), (r"\\cdot\b", "·"), (r"\\pm\b", "±"), (r"\\bmod\b", " mod "),
    (r"\\ldots\b", "…"), (r"\\dots\b", "…"), (r"\\cdots\b", "…"),
    (r"\\to\b", "→"), (r"\\rightarrow\b", "→"), (r"\\leftarrow\b", "←"),
    (r"\\infty\b", "∞"), (r"\\lfloor\b", "⌊"), (r"\\rfloor\b", "⌋"),
    (r"\\lceil\b", "⌈"), (r"\\rceil\b", "⌉"), (r"\\%", "%"), (r"\\\$", "$"),
]


def _math_inner(s: str) -> str:
    for pat, rep in _MATH_CMDS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"<sup>\1</sup>", s)   # 10^{18} -> 10<sup>18</sup>
    s = re.sub(r"\^(-?[\w])", r"<sup>\1</sup>", s)        # 10^5 -> 10<sup>5</sup>
    s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)     # A_{k} -> A<sub>k</sub>
    s = re.sub(r"_([\w])", r"<sub>\1</sub>", s)           # X_s -> X<sub>s</sub>
    s = re.sub(r"\\[,;\s]", " ", s)                       # thin/med spaces
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)               # drop any unknown \command backslash
    return s.replace("{", "").replace("}", "")


def _mathify(escaped: str) -> str:
    escaped = re.sub(r"\\\((.+?)\\\)",
                     lambda m: f'<span class="math">{_math_inner(m.group(1))}</span>', escaped, flags=re.S)
    escaped = re.sub(r"\\\[(.+?)\\\]",
                     lambda m: f'<span class="math">{_math_inner(m.group(1))}</span>', escaped, flags=re.S)
    return escaped


def _inline(text: str) -> str:
    # Escape first, then re-introduce the small set of inline constructs.
    out = html.escape(text)
    # inline LaTeX math \(...\) -> Unicode/sup/sub (before code so `\(` inside code stays literal)
    out = _mathify(out)
    # inline code: `...`
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    # bold: **...**
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    # italic: *...*  (avoid matching bold leftovers)
    out = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", out)
    # links: [text](url)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                 r'<a href="\2" target="_blank" rel="noopener">\1</a>', out)
    return out


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
