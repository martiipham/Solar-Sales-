#!/usr/bin/env python3
"""Solar Swarm — Branded PDF Generator

Converts all markdown docs to professionally branded PDFs using
Chrome headless rendering. Outputs to docs/pdf/.

Brand palette (matching swarm-board):
  Background:  #050810
  Surface:     #0D1117
  Border:      #1E2D3D
  Cyan:        #22D3EE
  Amber:       #F59E0B
  Green:       #4ADE80
  White text:  #F8FAFC
  Muted text:  #94A3B8

Usage:
    python docs/generate_pdfs.py
    python docs/generate_pdfs.py --doc architecture  # single doc
    python docs/generate_pdfs.py --bundle            # merge into bundles
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DOCS_DIR = Path(__file__).parent
PDF_DIR = DOCS_DIR / "pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ── Document bundles ──────────────────────────────────────────────────────────
BUNDLES = {
    "Solar_Swarm_Technical_Reference": [
        "README",
        "architecture",
        "agents",
        "memory-database",
        "data-collection",
        "api-reference",
        "swarm-board",
    ],
    "Solar_Swarm_Business_Guide": [
        "business-overview",
        "sales-playbook",
        "client-onboarding",
        "cost-tracking",
        "troubleshooting",
    ],
    "Solar_Swarm_Operations_Manual": [
        "setup-guide",
        "change-management",
        "deployment-checklist",
        "rollback-procedures",
        "crm-integrations",
        "capital-allocation",
        "voice-ai",
    ],
}

# ── HTML template ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:        #050810;
    --surface:   #0D1117;
    --surface2:  #111827;
    --border:    #1E2D3D;
    --cyan:      #22D3EE;
    --amber:     #F59E0B;
    --green:     #4ADE80;
    --red:       #F87171;
    --white:     #F8FAFC;
    --muted:     #94A3B8;
    --text:      #CBD5E1;
  }}

  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* ── Page layout ── */
  .page {{
    max-width: 740px;
    margin: 0 auto;
    padding: 32px 40px 48px;
  }}

  /* ── Header / wordmark ── */
  .doc-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 20px;
    margin-bottom: 28px;
    border-bottom: 1px solid var(--border);
  }}

  .wordmark {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13pt;
    font-weight: 500;
    letter-spacing: 0.08em;
    color: var(--cyan);
  }}

  .wordmark span {{
    color: var(--muted);
    font-weight: 300;
  }}

  .doc-meta {{
    text-align: right;
    font-size: 8pt;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
  }}

  /* ── Typography ── */
  h1 {{
    font-size: 22pt;
    font-weight: 700;
    color: var(--white);
    margin-bottom: 8px;
    line-height: 1.2;
  }}

  h2 {{
    font-size: 14pt;
    font-weight: 600;
    color: var(--cyan);
    margin-top: 32px;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
  }}

  h3 {{
    font-size: 11pt;
    font-weight: 600;
    color: var(--amber);
    margin-top: 20px;
    margin-bottom: 8px;
  }}

  h4 {{
    font-size: 10pt;
    font-weight: 600;
    color: var(--white);
    margin-top: 16px;
    margin-bottom: 6px;
  }}

  p {{
    margin-bottom: 10px;
    color: var(--text);
  }}

  /* ── Links ── */
  a {{ color: var(--cyan); text-decoration: none; }}

  /* ── Lists ── */
  ul, ol {{
    padding-left: 20px;
    margin-bottom: 10px;
  }}

  li {{
    margin-bottom: 4px;
    color: var(--text);
  }}

  li > strong {{ color: var(--white); }}

  /* ── Code ── */
  code {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 8.5pt;
    background: var(--surface2);
    color: var(--green);
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid var(--border);
  }}

  pre {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--cyan);
    border-radius: 6px;
    padding: 14px 16px;
    margin: 14px 0;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 8pt;
    line-height: 1.5;
    color: var(--green);
  }}

  pre code {{
    background: none;
    border: none;
    padding: 0;
    color: inherit;
    font-size: inherit;
  }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 9pt;
  }}

  thead tr {{
    background: var(--surface2);
    border-bottom: 2px solid var(--cyan);
  }}

  th {{
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
    color: var(--white);
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}

  td {{
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background: rgba(30, 45, 61, 0.3);
  }}

  /* ── Blockquotes / callouts ── */
  blockquote {{
    border-left: 3px solid var(--amber);
    background: rgba(245, 158, 11, 0.05);
    padding: 10px 14px;
    margin: 14px 0;
    border-radius: 0 6px 6px 0;
  }}

  blockquote p {{
    margin: 0;
    color: var(--amber);
    font-style: italic;
  }}

  /* ── Horizontal rule ── */
  hr {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 24px 0;
  }}

  /* ── Strong / em ── */
  strong {{ color: var(--white); font-weight: 600; }}
  em {{ color: var(--muted); font-style: italic; }}

  /* ── Footer ── */
  .doc-footer {{
    margin-top: 48px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 7.5pt;
    color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
  }}

  .footer-brand {{ color: var(--cyan); }}

  /* ── Print ── */
  @media print {{
    html, body {{ background: var(--bg); }}
    .page {{ padding: 24px 32px; }}
    h2 {{ page-break-after: avoid; }}
    pre, table {{ page-break-inside: avoid; }}
    .doc-header {{ page-break-after: avoid; }}
  }}

  @page {{
    size: A4;
    margin: 15mm 12mm 18mm;
  }}
</style>
</head>
<body>
<div class="page">

  <div class="doc-header">
    <div class="wordmark">SOLAR<span>▸</span>SWARM</div>
    <div class="doc-meta">
      <div>{category}</div>
      <div>Martin Pham | Perth, AU</div>
    </div>
  </div>

  <div class="content">
    {content}
  </div>

  <div class="doc-footer">
    <div class="footer-brand">SOLAR▸SWARM</div>
    <div>Confidential — {date}</div>
    <div>v2.0</div>
  </div>

</div>
</body>
</html>"""


def md_to_html(md_text: str) -> str:
    """Convert markdown to HTML. Uses Python stdlib only (no extra deps)."""

    lines = md_text.split("\n")
    html_lines = []
    in_code_block = False
    code_lang = ""
    code_buf = []
    in_table = False
    in_list = None  # 'ul' or 'ol'
    list_buf = []

    def flush_list():
        nonlocal in_list, list_buf
        if list_buf:
            tag = in_list
            html_lines.append(f"<{tag}>")
            for item in list_buf:
                html_lines.append(f"  <li>{item}</li>")
            html_lines.append(f"</{tag}>")
        list_buf = []
        in_list = None

    def flush_table(table_lines):
        html_lines.append('<table>')
        for i, row in enumerate(table_lines):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if i == 0:
                html_lines.append("<thead><tr>")
                for c in cells:
                    html_lines.append(f"  <th>{inline(c)}</th>")
                html_lines.append("</tr></thead><tbody>")
            elif re.match(r"[\|\s\-:]+$", row):
                continue  # separator row
            else:
                html_lines.append("<tr>")
                for c in cells:
                    html_lines.append(f"  <td>{inline(c)}</td>")
                html_lines.append("</tr>")
        html_lines.append("</tbody></table>")

    def inline(text: str) -> str:
        """Process inline markdown."""
        # Bold+italic
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        # Code
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        # Link
        text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
        return text

    table_buf = []

    for raw_line in lines:
        line = raw_line.rstrip()

        # ── Code blocks ──
        if line.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "\n".join(code_buf)
                html_lines.append(f"<pre><code>{code_text}</code></pre>")
                code_buf = []
            else:
                flush_list()
                if table_buf:
                    flush_table(table_buf)
                    table_buf = []
                    in_table = False
                in_code_block = True
                code_lang = line[3:].strip()
            continue

        if in_code_block:
            code_buf.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # ── Tables ──
        is_table_row = line.startswith("|") and line.endswith("|")
        if is_table_row:
            flush_list()
            if not in_table:
                in_table = True
                table_buf = []
            table_buf.append(line)
            continue
        else:
            if in_table:
                flush_table(table_buf)
                table_buf = []
                in_table = False

        # ── Headings ──
        h_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if h_match:
            flush_list()
            level = len(h_match.group(1))
            text = inline(h_match.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # ── HR ──
        if re.match(r"^---+$", line.strip()):
            flush_list()
            html_lines.append("<hr>")
            continue

        # ── Blockquote ──
        if line.startswith("> "):
            flush_list()
            text = inline(line[2:])
            html_lines.append(f"<blockquote><p>{text}</p></blockquote>")
            continue

        # ── Unordered list ──
        ul_match = re.match(r"^(\s*)[-*]\s+(.+)$", line)
        if ul_match:
            text = inline(ul_match.group(2))
            if in_list != "ul":
                flush_list()
                in_list = "ul"
            list_buf.append(text)
            continue

        # ── Ordered list ──
        ol_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ol_match:
            text = inline(ol_match.group(1))
            if in_list != "ol":
                flush_list()
                in_list = "ol"
            list_buf.append(text)
            continue

        # ── Regular paragraph ──
        flush_list()
        if line.strip():
            html_lines.append(f"<p>{inline(line)}</p>")
        else:
            html_lines.append("")

    flush_list()
    if table_buf:
        flush_table(table_buf)
    if code_buf:
        html_lines.append(f"<pre><code>{'<br>'.join(code_buf)}</code></pre>")

    return "\n".join(html_lines)


def doc_category(stem: str) -> str:
    """Return the document category label."""
    cats = {
        "README": "Master Index",
        "architecture": "Technical Reference",
        "agents": "Technical Reference",
        "memory-database": "Technical Reference",
        "data-collection": "Technical Reference",
        "api-reference": "API Reference",
        "swarm-board": "Technical Reference",
        "crm-integrations": "Integration Guide",
        "capital-allocation": "Technical Reference",
        "voice-ai": "Integration Guide",
        "setup-guide": "Operations",
        "change-management": "Change Management",
        "deployment-checklist": "Change Management",
        "rollback-procedures": "Change Management",
        "business-overview": "Business",
        "sales-playbook": "Business",
        "client-onboarding": "Client Guide",
        "cost-tracking": "Operations",
        "troubleshooting": "Operations",
    }
    return cats.get(stem, "Documentation")


def render_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Render HTML to PDF using Chrome headless."""
    if not os.path.exists(CHROME):
        print(f"  ERROR: Chrome not found at {CHROME}")
        return False

    cmd = [
        CHROME,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-software-rasterizer",
        f"--print-to-pdf={pdf_path}",
        "--print-to-pdf-no-header",
        str(html_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ERROR: Chrome returned {result.returncode}")
        if result.stderr:
            print(f"  {result.stderr[:200]}")
        return False
    return True


def generate_single(stem: str) -> Path | None:
    """Generate a single PDF from a markdown file."""
    md_path = DOCS_DIR / f"{stem}.md"
    if not md_path.exists():
        print(f"  SKIP: {stem}.md not found")
        return None

    md_text = md_path.read_text(encoding="utf-8")
    content_html = md_to_html(md_text)

    from datetime import date
    date_str = date.today().strftime("%d %b %Y")
    category = doc_category(stem)

    full_html = HTML_TEMPLATE.format(
        title=stem.replace("-", " ").title(),
        category=category,
        content=content_html,
        date=date_str,
    )

    pdf_path = PDF_DIR / f"{stem}.pdf"

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(full_html)
        html_tmp = Path(f.name)

    try:
        ok = render_pdf(html_tmp, pdf_path)
        if ok:
            size_kb = pdf_path.stat().st_size // 1024
            print(f"  OK  {stem}.pdf  ({size_kb} KB)")
            return pdf_path
        return None
    finally:
        html_tmp.unlink(missing_ok=True)


def generate_bundle(bundle_name: str, stems: list[str]) -> Path | None:
    """Generate a multi-document bundle PDF."""
    from datetime import date
    date_str = date.today().strftime("%d %b %Y")

    all_content = []
    for stem in stems:
        md_path = DOCS_DIR / f"{stem}.md"
        if not md_path.exists():
            print(f"  SKIP (missing): {stem}.md")
            continue
        md_text = md_path.read_text(encoding="utf-8")
        html = md_to_html(md_text)
        # Add page-break between documents
        all_content.append(f'<div style="page-break-before: always;">{html}</div>')

    if not all_content:
        return None

    combined = "\n".join(all_content)
    full_html = HTML_TEMPLATE.format(
        title=bundle_name.replace("_", " "),
        category="Bundle",
        content=combined,
        date=date_str,
    )

    pdf_path = PDF_DIR / f"{bundle_name}.pdf"

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(full_html)
        html_tmp = Path(f.name)

    try:
        ok = render_pdf(html_tmp, pdf_path)
        if ok:
            size_kb = pdf_path.stat().st_size // 1024
            print(f"  OK  {bundle_name}.pdf  ({size_kb} KB)")
            return pdf_path
        return None
    finally:
        html_tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Generate branded PDFs for Solar Swarm docs")
    parser.add_argument("--doc", help="Generate a single doc (stem name, e.g. architecture)")
    parser.add_argument("--bundle", action="store_true", help="Generate bundle PDFs only")
    parser.add_argument("--all", action="store_true", default=True, help="Generate all individual PDFs (default)")
    args = parser.parse_args()

    PDF_DIR.mkdir(exist_ok=True)

    print("\n╔══════════════════════════════════════════╗")
    print("║   SOLAR▸SWARM  PDF Generator             ║")
    print("╚══════════════════════════════════════════╝\n")

    if args.doc:
        print(f"Generating: {args.doc}")
        generate_single(args.doc)
    elif args.bundle:
        print("Generating bundles...")
        for name, stems in BUNDLES.items():
            print(f"\n[ {name.replace('_', ' ')} ]")
            generate_bundle(name, stems)
    else:
        # Generate all individual PDFs
        md_files = sorted(DOCS_DIR.glob("*.md"))
        stems = [f.stem for f in md_files if f.name != "generate_pdfs.py"]

        print(f"Generating {len(stems)} individual PDFs...")
        generated = []
        for stem in stems:
            result = generate_single(stem)
            if result:
                generated.append(result)

        print(f"\nGenerating 3 bundles...")
        for name, bundle_stems in BUNDLES.items():
            print(f"\n[ {name.replace('_', ' ')} ]")
            generate_bundle(name, bundle_stems)

        print(f"\n{'─'*44}")
        print(f"Generated {len(generated)}/{len(stems)} individual PDFs")
        print(f"Output: {PDF_DIR}")
        print()


if __name__ == "__main__":
    main()
