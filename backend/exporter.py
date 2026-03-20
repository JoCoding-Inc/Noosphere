from __future__ import annotations
import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path


def _escape_typst_string(s: str) -> str:
    """Typst 문자열 리터럴 안에서 사용할 수 있도록 이스케이프."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_typst_markup(s: str) -> str:
    """Typst 마크업 모드에서 특수문자 이스케이프."""
    s = s.replace("\\", "\\\\")
    s = s.replace("#", "\\#")
    s = s.replace("@", "\\@")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    return s


def _inline_md(text: str) -> str:
    """인라인 마크다운 → Typst 변환."""
    text = text.replace("\\", "\\\\")
    text = text.replace("#", "\\#")
    text = text.replace("@", "\\@")
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'#link("{m.group(2)}")[{m.group(1)}]',
        text,
    )
    _BOLD = "\x00B\x00"
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: f"{_BOLD}{m.group(1)}{_BOLD}", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"_\1_", text)
    text = text.replace(_BOLD, "*")
    text = re.sub(r"`([^`]+)`", lambda m: f'`{m.group(1)}`', text)
    return text


def _parse_table_row(line: str) -> list[str]:
    line = line.strip().strip("|")
    return [c.strip() for c in line.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return all(re.match(r"^[-:]+$", c) for c in cells if c)


def _emit_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    data_rows = [r for r in rows if not _is_separator_row(r)]
    if not data_rows:
        return ""
    header = data_rows[0]
    body = data_rows[1:]
    ncols = len(header)
    col_spec = ", ".join(["1fr"] * ncols)
    lines = [
        "#table(",
        f"  columns: ({col_spec}),",
        "  stroke: 0.5pt + luma(200),",
        "  fill: (_, y) => if y == 0 { luma(235) } else { white },",
    ]
    header_cells = ", ".join(f"[*{_inline_md(c)}*]" for c in header)
    lines.append(f"  {header_cells},")
    for row in body:
        padded = row + [""] * max(0, ncols - len(row))
        cells = ", ".join(f"[{_inline_md(c)}]" for c in padded[:ncols])
        lines.append(f"  {cells},")
    lines.append(")")
    return "\n".join(lines)


def _md_to_typst(text: str) -> str:
    """마크다운 → Typst 변환"""
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    code_lang = "text"
    code_lines: list[str] = []
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        if table_rows:
            out.append(_emit_table(table_rows))
            out.append("")
            table_rows.clear()

    for line in lines:
        if line.startswith("```"):
            flush_table()
            if not in_code:
                code_lang = line[3:].strip() or "text"
                in_code = True
                code_lines = []
            else:
                content = _escape_typst_string("\n".join(code_lines))
                out.append(f'#raw(lang: "{code_lang}", block: true, "{content}")')
                in_code = False
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if re.match(r"^\s*\|", line):
            cells = _parse_table_row(line)
            if cells:
                table_rows.append(cells)
            continue
        else:
            flush_table()
        if re.match(r"^[-*_]{3,}$", line.strip()):
            out.append("#line(length: 100%)")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            content = _inline_md(m.group(2))
            out.append("=" * level + " " + content)
            continue
        m = re.match(r"^(\s*)\d+\.\s+(.*)", line)
        if m:
            indent = len(m.group(1)) // 2
            content = _inline_md(m.group(2))
            out.append("  " * indent + "+ " + content)
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)", line)
        if m:
            indent = len(m.group(1)) // 2
            content = _inline_md(m.group(2))
            out.append("  " * indent + "- " + content)
            continue
        if line.startswith("> "):
            out.append(f"#quote[{_inline_md(line[2:])}]")
            continue
        if not line.strip():
            out.append("")
            continue
        out.append(_inline_md(line))

    flush_table()
    return "\n".join(out)


_LANG_SETTINGS: dict[str, tuple[str, str]] = {
    "Korean":     ("ko", '"Noto Serif CJK KR", "Noto Sans CJK KR", "Noto Serif", "New Computer Modern"'),
    "Japanese":   ("ja", '"Noto Serif CJK JP", "Noto Sans CJK JP", "Noto Serif", "New Computer Modern"'),
    "Chinese":    ("zh", '"Noto Serif CJK SC", "Noto Sans CJK SC", "Noto Serif", "New Computer Modern"'),
    "English":    ("en", '"New Computer Modern", "Noto Serif"'),
    "Spanish":    ("es", '"New Computer Modern", "Noto Serif"'),
    "French":     ("fr", '"New Computer Modern", "Noto Serif"'),
    "German":     ("de", '"New Computer Modern", "Noto Serif"'),
    "Portuguese": ("pt", '"New Computer Modern", "Noto Serif"'),
}


def _build_typst(
    domain: str,
    idea_text: str,
    analysis_md: str | None,
    report_md: str,
    language: str = "English",
) -> str:
    lang_code, fonts = _LANG_SETTINGS.get(language, _LANG_SETTINGS["English"])
    date_str = datetime.now().strftime("%Y-%m-%d")
    idea_snippet = _escape_typst_markup(idea_text[:200])
    analysis_body = _md_to_typst(analysis_md) if analysis_md else "_분석 보고서 없음_"
    sim_body = _md_to_typst(report_md) if report_md else "_시뮬레이션 보고서 없음_"

    return f"""#set document(title: "Noosphere Report — {domain}", date: auto)
#set page(
  margin: (x: 2.5cm, y: 3cm),
  numbering: "1 / 1",
  header: [
    #set text(size: 9pt, fill: luma(120))
    #grid(columns: (1fr, 1fr),
      [Noosphere Report],
      align(right)[{domain}]
    )
    #line(length: 100%, stroke: luma(200))
  ],
)
#set text(font: ({fonts}), size: 11pt, lang: "{lang_code}")
#set heading(numbering: "1.")
#set par(justify: true, leading: 0.8em)
#set table(inset: 6pt)
#show heading.where(level: 1): it => {{
  v(1.2em)
  text(size: 16pt, weight: "bold", it)
  v(0.4em)
}}
#show heading.where(level: 2): it => {{
  v(0.8em)
  text(size: 13pt, weight: "bold", it)
  v(0.3em)
}}

// ── 표지 ──────────────────────────────────────────────
#align(center)[
  #v(4cm)
  #text(size: 28pt, weight: "bold")[Noosphere]
  #v(0.4em)
  #text(size: 16pt, fill: luma(80))[Product Validation Report]
  #v(1.2em)
  #rect(width: 60%, stroke: luma(200))[
    #pad(0.6em)[
      #text(size: 12pt, style: "italic")["{idea_snippet}..."]
    ]
  ]
  #v(1em)
  #text(size: 12pt, fill: luma(100))[Domain: *{domain}*]
  #v(0.4em)
  #text(size: 11pt, fill: luma(120))[{date_str}]
]

#pagebreak()

// ── 분석 보고서 ──────────────────────────────────────
= Analysis Report

{analysis_body}

#pagebreak()

// ── 시뮬레이션 보고서 ────────────────────────────────
= Simulation Report

{sim_body}
"""


async def build_pdf(
    report_md: str,
    input_text: str,
    sim_id: str,
    domain: str = "",
    language: str = "English",
    analysis_md: str | None = None,
) -> bytes:
    typ_content = _build_typst(
        domain=domain or input_text[:60],
        idea_text=input_text,
        analysis_md=analysis_md,
        report_md=report_md,
        language=language,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "report.typ"
        out = Path(tmpdir) / "report.pdf"
        src.write_text(typ_content, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            "typst", "compile", str(src), str(out),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"typst compile failed: {stderr.decode()}")

        return out.read_bytes()
