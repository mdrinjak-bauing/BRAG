"""Chunking: paragraph-level sliding window with overlap, table splitting
with header replication, and a hard splitter for pathological inputs.

The strategies and limits are ported from a production system where they
were validated against a retrieval gold standard:
- paragraphs are never torn apart unless a single paragraph exceeds the limit
- long markdown tables are split by rows, replicating the header per part
- a hard splitter handles text without paragraph/newline boundaries (OCR)
"""


def hard_split(s: str, max_chars: int) -> list[str]:
    """Last-resort splitter for strings without paragraph boundaries.
    Prefers newline, then sentence end, then whitespace, else cuts hard."""
    if max_chars < 200:
        max_chars = 200  # safety floor: avoids no-progress loops
    if len(s) <= max_chars:
        return [s]
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        end = min(i + max_chars, n)
        if end < n:
            window_start = i + max_chars // 2
            for sep in ("\n", ". ", "! ", "? ", "; ", " "):
                pos = s.rfind(sep, window_start, end)
                if pos > i:
                    end = pos + len(sep)
                    break
        piece = s[i:end].strip()
        if piece:
            out.append(piece)
        i = end
    return out


def split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split long text at paragraph level with overlap."""
    raw_paragraphs = [p for p in text.split("\n\n") if p.strip()]
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        if len(p) > max_chars:
            paragraphs.extend(hard_split(p, max_chars))
        else:
            paragraphs.append(p)

    chunks, current, current_len = [], [], 0
    for para in paragraphs:
        if current and current_len + len(para) > max_chars:
            chunks.append("\n\n".join(current))
            tail, tail_len = [], 0
            for prev in reversed(current):
                if tail_len + len(prev) <= overlap:
                    tail.insert(0, prev)
                    tail_len += len(prev)
                else:
                    break
            current, current_len = tail, tail_len
        current.append(para)
        current_len += len(para)
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text]


def split_long_table(table_md: str, max_chars: int) -> list[str]:
    """Split a long markdown table by rows, replicating the header per part.
    Preserves any explanatory text before the first '|' line."""
    if len(table_md) <= max_chars:
        return [table_md]

    lines = table_md.split("\n")
    preamble_end = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            preamble_end = i
            break
    preamble = "\n".join(lines[:preamble_end]).rstrip() if preamble_end > 0 else ""

    header_lines: list[str] = []
    body_start = -1
    for i in range(max(preamble_end, 0), len(lines)):
        s = lines[i].strip()
        if s.startswith("|"):
            header_lines.append(lines[i])
            if "---" in s:
                body_start = i + 1
                break
        elif header_lines:
            break

    if body_start < 0 or not header_lines:
        return [c for c in hard_split(table_md, max_chars) if c.strip()]

    header = "\n".join(header_lines)
    header_overhead = len(header) + 1
    parts: list[str] = []
    current: list[str] = []
    current_len = header_overhead
    for line in lines[body_start:]:
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            parts.append(header + "\n" + "\n".join(current))
            current, current_len = [line], header_overhead + line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        parts.append(header + "\n" + "\n".join(current))

    # Re-check: a single row with huge cells can still exceed the limit
    rechecked: list[str] = []
    for part in parts:
        if len(part) > max_chars:
            sub_limit = max_chars - header_overhead
            if sub_limit < 500:
                rechecked.extend(hard_split(part, max_chars))
            else:
                body = part[len(header):].lstrip("\n") if part.startswith(header) else part
                for sub in hard_split(body, sub_limit):
                    rechecked.append(header + "\n" + sub)
        else:
            rechecked.append(part)
    parts = rechecked

    if preamble and parts:
        parts[0] = preamble + "\n\n" + parts[0]
    if len(parts) > 1:
        for i in range(1, len(parts)):
            parts[i] = f"_(table continued, part {i + 1}/{len(parts)})_\n\n{parts[i]}"
    return parts
