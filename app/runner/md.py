"""Tiny dependency-free Markdown -> HTML renderer.

Scope: exactly what problem statements and editorials use — headings, paragraphs, fenced and inline
code, bold/italic, unordered/ordered lists, pipe tables, blockquotes, horizontal rules. Not a full
CommonMark implementation; deliberately small so the app needs no pip installs.
"""
import html
import re


def _inline(text: str) -> str:
    # Escape first, then re-introduce the small set of inline constructs.
    out = html.escape(text)
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
