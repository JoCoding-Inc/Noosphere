from __future__ import annotations
import asyncio
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _escape_typst_string(s: str) -> str:
    """Typst 문자열 리터럴 안에서 사용할 수 있도록 이스케이프."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_typst_markup(s: str) -> str:
    """Typst 마크업 모드에서 특수문자 이스케이프."""
    s = s.replace("\\", "\\\\")
    s = s.replace("#", "\\#")
    s = s.replace("@", "\\@")
    s = s.replace("$", "\\$")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    return s


def _inline_md(text: str) -> str:
    """인라인 마크다운 → Typst 변환."""
    text = text.replace("\\", "\\\\")
    text = text.replace("#", "\\#")
    text = text.replace("@", "\\@")
    text = text.replace("$", "\\$")
    # Process Markdown links first, protect them from bracket escaping
    _links: list[str] = []
    def _replace_link(m: re.Match) -> str:
        _links.append(f'#link("{m.group(2).replace(chr(34), chr(92)+chr(34))}")[{m.group(1)}]')
        return f"\x00LNK{len(_links) - 1}\x00"
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, text)
    # Escape bare square brackets (common in LLM output, break Typst content blocks)
    text = text.replace("[", "\\[").replace("]", "\\]")
    # Restore protected links
    for i, lnk in enumerate(_links):
        text = text.replace(f"\x00LNK{i}\x00", lnk)
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


# (언어코드, 폰트 목록) — Noto CJK 우선, macOS/Windows 시스템 폰트 fallback
_LANG_SETTINGS: dict[str, tuple[str, str, dict[str, str]]] = {
    "Korean": (
        "ko",
        '"Noto Serif CJK KR", "Noto Sans CJK KR", "Apple SD Gothic Neo", "AppleGothic", "Malgun Gothic", "Noto Serif", "New Computer Modern"',
        {
            "report_title": "제품 검증 보고서",
            "section_analysis": "분석 보고서",
            "section_simulation": "시뮬레이션 보고서",
            "section_params": "시뮬레이션 설정",
            "param_domain": "도메인",
            "param_language": "언어",
            "param_rounds": "라운드",
            "param_agents": "에이전트",
            "param_platforms": "플랫폼",
            "param_date": "생성일",
            "no_analysis": "_분석 보고서 없음_",
            "no_simulation": "_시뮬레이션 보고서 없음_",
            "section_final_report": "최종 보고서",
            "no_final_report": "_최종 보고서 없음_",
            "section_gtm": "런치 전략",
            "no_gtm": "_런치 전략 없음_",
        },
    ),
    "Japanese": (
        "ja",
        '"Noto Serif CJK JP", "Noto Sans CJK JP", "Hiragino Mincho ProN", "Hiragino Kaku Gothic ProN", "Yu Mincho", "Noto Serif", "New Computer Modern"',
        {
            "report_title": "製品検証レポート",
            "section_analysis": "分析レポート",
            "section_simulation": "シミュレーションレポート",
            "section_params": "シミュレーション設定",
            "param_domain": "ドメイン",
            "param_language": "言語",
            "param_rounds": "ラウンド",
            "param_agents": "エージェント",
            "param_platforms": "プラットフォーム",
            "param_date": "生成日",
            "no_analysis": "_分析レポートなし_",
            "no_simulation": "_シミュレーションレポートなし_",
            "section_final_report": "最終レポート",
            "no_final_report": "_最終レポートなし_",
            "section_gtm": "ローンチ戦略",
            "no_gtm": "_ローンチ戦略なし_",
        },
    ),
    "Chinese": (
        "zh",
        '"Noto Serif CJK SC", "Noto Sans CJK SC", "STSong", "PingFang SC", "SimSun", "Noto Serif", "New Computer Modern"',
        {
            "report_title": "产品验证报告",
            "section_analysis": "分析报告",
            "section_simulation": "模拟报告",
            "section_params": "模拟设置",
            "param_domain": "领域",
            "param_language": "语言",
            "param_rounds": "轮次",
            "param_agents": "智能体",
            "param_platforms": "平台",
            "param_date": "生成日期",
            "no_analysis": "_无分析报告_",
            "no_simulation": "_无模拟报告_",
            "section_final_report": "最终报告",
            "no_final_report": "_无最终报告_",
            "section_gtm": "上市策略",
            "no_gtm": "_无上市策略_",
        },
    ),
    "Spanish": (
        "es",
        '"New Computer Modern", "Noto Serif"',
        {
            "report_title": "Informe de Validación de Producto",
            "section_analysis": "Informe de Análisis",
            "section_simulation": "Informe de Simulación",
            "section_params": "Configuración de Simulación",
            "param_domain": "Dominio",
            "param_language": "Idioma",
            "param_rounds": "Rondas",
            "param_agents": "Agentes",
            "param_platforms": "Plataformas",
            "param_date": "Fecha",
            "no_analysis": "_Sin informe de análisis_",
            "no_simulation": "_Sin informe de simulación_",
            "section_final_report": "Informe Final",
            "no_final_report": "_Sin informe final_",
            "section_gtm": "Estrategia de Lanzamiento",
            "no_gtm": "_Sin estrategia de lanzamiento_",
        },
    ),
    "French": (
        "fr",
        '"New Computer Modern", "Noto Serif"',
        {
            "report_title": "Rapport de Validation Produit",
            "section_analysis": "Rapport d'Analyse",
            "section_simulation": "Rapport de Simulation",
            "section_params": "Paramètres de Simulation",
            "param_domain": "Domaine",
            "param_language": "Langue",
            "param_rounds": "Tours",
            "param_agents": "Agents",
            "param_platforms": "Plateformes",
            "param_date": "Date",
            "no_analysis": "_Aucun rapport d'analyse_",
            "no_simulation": "_Aucun rapport de simulation_",
            "section_final_report": "Rapport Final",
            "no_final_report": "_Aucun rapport final_",
            "section_gtm": "Stratégie de Lancement",
            "no_gtm": "_Aucune stratégie de lancement_",
        },
    ),
    "German": (
        "de",
        '"New Computer Modern", "Noto Serif"',
        {
            "report_title": "Produktvalidierungsbericht",
            "section_analysis": "Analysebericht",
            "section_simulation": "Simulationsbericht",
            "section_params": "Simulationsparameter",
            "param_domain": "Domäne",
            "param_language": "Sprache",
            "param_rounds": "Runden",
            "param_agents": "Agenten",
            "param_platforms": "Plattformen",
            "param_date": "Datum",
            "no_analysis": "_Kein Analysebericht_",
            "no_simulation": "_Kein Simulationsbericht_",
            "section_final_report": "Abschlussbericht",
            "no_final_report": "_Kein Abschlussbericht_",
            "section_gtm": "Launch-Strategie",
            "no_gtm": "_Keine Launch-Strategie_",
        },
    ),
    "Portuguese": (
        "pt",
        '"New Computer Modern", "Noto Serif"',
        {
            "report_title": "Relatório de Validação de Produto",
            "section_analysis": "Relatório de Análise",
            "section_simulation": "Relatório de Simulação",
            "section_params": "Configurações de Simulação",
            "param_domain": "Domínio",
            "param_language": "Idioma",
            "param_rounds": "Rodadas",
            "param_agents": "Agentes",
            "param_platforms": "Plataformas",
            "param_date": "Data",
            "no_analysis": "_Sem relatório de análise_",
            "no_simulation": "_Sem relatório de simulação_",
            "section_final_report": "Relatório Final",
            "no_final_report": "_Sem relatório final_",
            "section_gtm": "Estratégia de Lançamento",
            "no_gtm": "_Sem estratégia de lançamento_",
        },
    ),
    "English": (
        "en",
        '"New Computer Modern", "Noto Serif"',
        {
            "report_title": "Product Validation Report",
            "section_analysis": "Analysis Report",
            "section_simulation": "Simulation Report",
            "section_params": "Simulation Parameters",
            "param_domain": "Domain",
            "param_language": "Language",
            "param_rounds": "Rounds",
            "param_agents": "Agents",
            "param_platforms": "Platforms",
            "param_date": "Date",
            "no_analysis": "_No analysis report_",
            "no_simulation": "_No simulation report_",
            "section_final_report": "Final Report",
            "no_final_report": "_No final report_",
            "section_gtm": "Launch Strategy",
            "no_gtm": "_No launch strategy available_",
        },
    ),
}


def _build_report_json_section(report_json: dict | None, labels: dict[str, str]) -> str:
    """Build Typst markup for verdict, segments, and criticism_clusters from report_json."""
    if not report_json:
        return ""
    parts: list[str] = []

    verdict = report_json.get("verdict")
    if verdict:
        parts.append(f'== Verdict\n\n*{_escape_typst_markup(str(verdict))}*')

    segments = report_json.get("segments", [])
    if segments:
        seg_lines = ["== Segments\n"]
        for seg in segments:
            name = _escape_typst_markup(seg.get("name", ""))
            desc = _escape_typst_markup(seg.get("summary", seg.get("description", ""))[:200])
            seg_lines.append(f"- *{name}*: {desc}")
        parts.append("\n".join(seg_lines))

    praises = report_json.get("praise_clusters", [])
    if praises:
        praise_lines = ["== Praise Clusters\n"]
        for p in praises:
            theme = _escape_typst_markup(p.get("theme", ""))
            count = p.get("count", 0)
            praise_lines.append(f"- *{theme}* ({count} mentions)")
        parts.append("\n".join(praise_lines))

    criticisms = report_json.get("criticism_clusters", [])
    if criticisms:
        crit_lines = ["== Criticism Clusters\n"]
        for c in criticisms:
            theme = _escape_typst_markup(c.get("theme", ""))
            count = c.get("count", 0)
            crit_lines.append(f"- *{theme}* ({count} mentions)")
        parts.append("\n".join(crit_lines))

    improvements = report_json.get("improvements", [])
    if improvements:
        imp_lines = ["== Improvements\n"]
        for imp in improvements:
            suggestion = _escape_typst_markup(imp.get("suggestion", ""))
            frequency = imp.get("frequency", 0)
            imp_lines.append(f"- *{suggestion}* ({frequency} mentions)")
        parts.append("\n".join(imp_lines))

    if not parts:
        return ""
    return "\n\n".join(parts)


def _build_personas_section(personas: dict | None) -> str:
    """Build Typst markup for participant demographics from personas dict."""
    if not personas:
        return ""
    # Flatten all personas across platforms
    all_personas: list[dict] = []
    for platform_personas in personas.values():
        if isinstance(platform_personas, list):
            all_personas.extend(platform_personas)
        elif isinstance(platform_personas, dict):
            # handle dict-of-dicts
            for p in platform_personas.values():
                if isinstance(p, dict):
                    all_personas.append(p)
    if not all_personas:
        return ""

    total = len(all_personas)

    # seniority 분포
    seniority_counts: dict[str, int] = {}
    for p in all_personas:
        level = p.get("seniority") or p.get("level") or "unknown"
        if isinstance(level, str) and level.strip():
            key = level.strip().capitalize()
            seniority_counts[key] = seniority_counts.get(key, 0) + 1

    # affiliation 분포
    affiliation_counts: dict[str, int] = {}
    for p in all_personas:
        aff = p.get("affiliation") or p.get("org_type") or p.get("company_type") or "unknown"
        if isinstance(aff, str) and aff.strip():
            key = aff.strip().capitalize()
            affiliation_counts[key] = affiliation_counts.get(key, 0) + 1

    parts: list[str] = [
        "= Participant Profile\n",
        f"Total participants: *{total}*\n",
    ]

    if seniority_counts:
        parts.append("== Seniority Distribution\n")
        for level, count in sorted(seniority_counts.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100)
            parts.append(f"- *{_escape_typst_markup(level)}*: {count} ({pct}%)")

    if affiliation_counts:
        parts.append("\n== Affiliation Distribution\n")
        for aff, count in sorted(affiliation_counts.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100)
            parts.append(f"- *{_escape_typst_markup(aff)}*: {count} ({pct}%)")

    return "\n".join(parts)


def _build_sentiment_timeline_section(report_json: dict | None) -> str:
    """Build Typst markup for sentiment_timeline and platform_sentiment_timeline tables."""
    if not report_json:
        return ""
    parts: list[str] = []

    # Overall sentiment timeline
    timeline = report_json.get("sentiment_timeline", [])
    if isinstance(timeline, list) and len(timeline) >= 2:
        rows: list[str] = []
        rows.append("#table(")
        rows.append("  columns: (1fr, 1fr, 1fr, 1fr),")
        rows.append("  stroke: 0.5pt + luma(200),")
        rows.append("  fill: (_, y) => if y == 0 { luma(235) } else { white },")
        rows.append("  [*Round*], [*Positive*], [*Neutral*], [*Negative*],")
        for entry in timeline:
            rnd = entry.get("round", "")
            pos = entry.get("positive", 0)
            neu = entry.get("neutral", 0)
            neg = entry.get("negative", 0)
            rows.append(f"  [{rnd}], [{pos}], [{neu}], [{neg}],")
        rows.append(")")
        parts.append("== Sentiment Timeline\n\n" + "\n".join(rows))

    # Platform-specific sentiment timeline
    platform_timeline = report_json.get("platform_sentiment_timeline", {})
    if isinstance(platform_timeline, dict):
        for platform_name, p_timeline in platform_timeline.items():
            if not isinstance(p_timeline, list) or len(p_timeline) < 2:
                continue
            rows = []
            rows.append("#table(")
            rows.append("  columns: (1fr, 1fr, 1fr, 1fr),")
            rows.append("  stroke: 0.5pt + luma(200),")
            rows.append("  fill: (_, y) => if y == 0 { luma(235) } else { white },")
            escaped_name = _escape_typst_markup(platform_name)
            rows.append(f"  [*Round*], [*Positive*], [*Neutral*], [*Negative*],")
            for entry in p_timeline:
                rnd = entry.get("round", "")
                pos = entry.get("positive", 0)
                neu = entry.get("neutral", 0)
                neg = entry.get("negative", 0)
                rows.append(f"  [{rnd}], [{pos}], [{neu}], [{neg}],")
            rows.append(")")
            parts.append(f"== {escaped_name} Sentiment Timeline\n\n" + "\n".join(rows))

    if not parts:
        return ""
    return "\n\n".join(parts)


def _build_typst(
    domain: str,
    idea_text: str,
    analysis_md: str | None,
    report_md: str,
    language: str = "English",
    sim_params: dict | None = None,
    final_report_md: str | None = None,
    idea_title: str = "",
    gtm_md: str | None = None,
    report_json: dict | None = None,
    personas: dict | None = None,
) -> str:
    lang_code, fonts, labels = _LANG_SETTINGS.get(language, _LANG_SETTINGS["English"])
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    idea_snippet = _escape_typst_markup(idea_text[:200])
    domain_escaped = _escape_typst_markup(domain)
    title_escaped = _escape_typst_markup(idea_title) if idea_title else domain_escaped
    analysis_body = _md_to_typst(analysis_md) if analysis_md else labels["no_analysis"]
    # Fallback to final_report_md if sim report_md is missing (e.g. older DB rows)
    _sim_md = report_md or final_report_md or ""
    sim_body = _md_to_typst(_sim_md) if _sim_md else labels["no_simulation"]
    final_body = _md_to_typst(final_report_md) if final_report_md else labels["no_final_report"]
    gtm_body = _md_to_typst(gtm_md) if gtm_md else labels.get("no_gtm", "_No launch strategy available._")
    report_json_section = _build_report_json_section(report_json, labels)
    sentiment_timeline_section = _build_sentiment_timeline_section(report_json)

    params = sim_params or {}
    platforms_str = _escape_typst_markup(", ".join(params.get("platforms", [])) or "—")
    params_section = f"""= {labels["section_params"]}

#table(
  columns: (auto, 1fr),
  stroke: 0.5pt + luma(210),
  fill: (_, y) => if calc.odd(y) {{ luma(247) }} else {{ white }},
  [*{labels["param_domain"]}*],   [{domain_escaped}],
  [*{labels["param_language"]}*], [{language}],
  [*{labels["param_rounds"]}*],   [{params.get("num_rounds", "—")}],
  [*{labels["param_agents"]}*],   [{params.get("max_agents", "—")}],
  [*{labels["param_platforms"]}*],[{platforms_str}],
  [*{labels["param_date"]}*],     [{date_str}],
)"""

    personas_section = _build_personas_section(personas)

    report_title_upper = labels["report_title"].upper()

    return f"""#set document(title: "Noosphere — {title_escaped}", date: auto)

// ── jastylest-zh: CJK 폰트 + CJK-Latin 간격 자동 보정 ──
#set text(font: ({fonts}), size: 11pt, lang: "{lang_code}", cjk-latin-spacing: auto)
#set par(justify: true, leading: 0.88em, spacing: 1.35em)
#set table(inset: 8pt, stroke: 0.5pt + luma(210))
#set list(indent: 0.8em)
#set enum(indent: 0.8em)

// ── modern-technique-report: 헤딩 스타일 (블랙 테마) ─────
#set heading(numbering: none)
#show heading.where(level: 1): it => {{
  v(2em)
  block(
    width: 100%,
    stroke: (left: 4pt + black),
    inset: (left: 12pt, right: 8pt, y: 7pt),
    fill: luma(245),
  )[
    #text(size: 14pt, weight: "bold")[#it.body]
  ]
  v(0.35em)
}}
#show heading.where(level: 2): it => {{
  v(1.1em)
  text(size: 12pt, weight: "bold")[#it.body]
  v(-0.15em)
  line(length: 100%, stroke: 0.5pt + luma(215))
  v(0.1em)
}}
#show heading.where(level: 3): it => {{
  v(0.7em)
  text(size: 11pt, weight: "bold")[#it.body]
  v(0.05em)
}}

// ── TOC 스타일 ────────────────────────────────────────────
#show outline.entry.where(level: 1): it => {{
  v(0.35em)
  strong(it)
}}

// ── 페이지 레이아웃 ───────────────────────────────────────
#set page(
  margin: (x: 2.5cm, y: 3cm),
  header: context {{
    if counter(page).get().first() > 1 {{
      set text(size: 8.5pt, fill: luma(150))
      grid(
        columns: (1fr, auto),
        align: (left + horizon, right + horizon),
        [Noosphere],
        [{title_escaped}],
      )
      v(-0.45em)
      line(length: 100%, stroke: 0.4pt + luma(220))
    }}
  }},
  footer: context {{
    if counter(page).get().first() > 1 {{
      set text(size: 8pt, fill: luma(160))
      align(center)[#counter(page).display("1 / 1", both: true)]
    }}
  }},
)

// ── 표지 (modern-technique-report 블랙 밴드 스타일) ──────
#page(margin: 0pt, header: none, footer: none)[
  // 상단 블랙 밴드 ─ 브랜딩 + 도메인 제목
  #block(width: 100%, fill: black, inset: (x: 2.8cm, top: 4cm, bottom: 3cm))[
    #set text(fill: white)
    #text(size: 9pt, tracking: 4pt, fill: luma(155))[NOOSPHERE]
    #v(1em)
    #text(size: 26pt, weight: "bold")[{title_escaped}]
    #v(0.6em)
    #line(length: 3.5cm, stroke: 0.7pt + luma(95))
    #v(0.6em)
    #text(size: 11pt, tracking: 0.8pt, fill: luma(185))[{domain_escaped} · {report_title_upper}]
  ]
  // 하단 흰 영역 ─ 아이디어 인용 + 메타
  #block(width: 100%, fill: white, inset: (x: 2.8cm, top: 2.2cm, bottom: 2.5cm))[
    #rect(
      stroke: (left: 3pt + black, rest: none),
      inset: (left: 14pt, y: 9pt),
      width: 76%,
    )[
      #text(size: 10.5pt, style: "italic", fill: luma(65))["{idea_snippet}"]
    ]
    #v(2.8cm)
    #grid(
      columns: (auto, 1fr),
      row-gutter: 10pt,
      column-gutter: 20pt,
      text(size: 9pt, fill: luma(130))[{labels["param_domain"]}],
      text(size: 9pt, weight: "bold")[{domain_escaped}],
      text(size: 9pt, fill: luma(130))[{labels["param_date"]}],
      text(size: 9pt)[{date_str}],
    )
  ]
]

// ── 목차 ──────────────────────────────────────────────────
#outline(depth: 2, indent: 1.5em)

#pagebreak()

// ── 시뮬레이션 파라미터 ──────────────────────────────────
{params_section}

{"" if not personas_section else f"""#pagebreak()

// ── 참여자 프로필 ──────────────────────────────────────
{personas_section}
"""}{"" if not report_json_section else f"""#pagebreak()

// ── 시뮬레이션 데이터 요약 ──────────────────────────────
= Simulation Data Summary

{report_json_section}
"""}{"" if not sentiment_timeline_section else f"""#pagebreak()

// ── 감성 타임라인 ──────────────────────────────────────
= Sentiment Timeline

{sentiment_timeline_section}
"""}#pagebreak()

// ── 분석 보고서 ──────────────────────────────────────────
= {labels["section_analysis"]}

{analysis_body}

#pagebreak()

// ── 시뮬레이션 보고서 ────────────────────────────────────
= {labels["section_simulation"]}

{sim_body}

#pagebreak()

// ── GTM 전략 ──────────────────────────────────────────────
= {labels["section_gtm"]}

{gtm_body}

#pagebreak()

// ── 최종 보고서 ──────────────────────────────────────────
= {labels["section_final_report"]}

{final_body}
"""


async def build_pdf(
    report_md: str,
    input_text: str,
    sim_id: str,
    domain: str = "",
    language: str = "English",
    analysis_md: str | None = None,
    sim_params: dict | None = None,
    final_report_md: str | None = None,
    idea_title: str = "",
    gtm_md: str | None = None,
    report_json: dict | None = None,
    personas: dict | None = None,
) -> bytes:
    typ_content = _build_typst(
        domain=domain or input_text[:60],
        idea_text=input_text,
        analysis_md=analysis_md,
        report_md=report_md,
        language=language,
        sim_params=sim_params,
        final_report_md=final_report_md,
        idea_title=idea_title,
        gtm_md=gtm_md,
        report_json=report_json,
        personas=personas,
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
            err = stderr.decode(errors="replace")
            hint = ""
            if "unknown font family" in err and ("cjk" in err.lower() or "noto" in err.lower()):
                hint = " (hint: Noto CJK fonts not installed — Docker image needs fonts-noto-cjk)"
            raise RuntimeError(f"typst compile failed{hint}: {err}")

        return out.read_bytes()
