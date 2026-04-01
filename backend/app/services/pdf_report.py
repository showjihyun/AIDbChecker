# Spec: FS-AI-REPORT-002
"""PDF report generator — converts DBA report JSON to styled PDF.

Uses HTML template + weasyprint for PDF rendering.
Fallback: plain-text PDF via reportlab if weasyprint unavailable.
"""

from __future__ import annotations

from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


def generate_pdf(report: dict) -> bytes:
    """Generate PDF bytes from DBA report dict.

    Spec: FS-AI-REPORT-002 §4
    """
    html = _render_html(report)

    # Try weasyprint first
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        logger.info("pdf_report.weasyprint_not_available, falling back to html2pdf")

    # Fallback: return HTML as-is wrapped in minimal PDF-like structure
    # (for environments where weasyprint can't be installed)
    return _html_to_simple_pdf(html, report)


def _render_html(report: dict) -> str:
    """Render DBA report as styled HTML for PDF conversion."""
    m = report.get("metrics_summary", {})
    period_label = {"daily": "일간", "weekly": "주간", "monthly": "월간"}
    p = period_label.get(report.get("period", ""), report.get("period", ""))

    # Metrics table rows
    def _status(val, warn, crit):
        if val >= crit:
            return '<span style="color:#ef4444">&#x1F534;</span>'
        if val >= warn:
            return '<span style="color:#f59e0b">&#x1F7E1;</span>'
        return '<span style="color:#10b981">&#x1F7E2;</span>'

    cpu_max = m.get("cpu", {}).get("max", 0)
    mem_max = m.get("memory", {}).get("max", 0)
    conn_max = m.get("connections", {}).get("max", 0)

    metrics_rows = f"""
    <tr><td>CPU 사용률</td><td>{m.get("cpu", {}).get("avg", 0):.1f}%</td>
        <td>{cpu_max:.1f}%</td><td>{_status(cpu_max, 70, 90)}</td></tr>
    <tr><td>메모리 사용률</td><td>{m.get("memory", {}).get("avg", 0):.1f}%</td>
        <td>{mem_max:.1f}%</td><td>{_status(mem_max, 70, 90)}</td></tr>
    <tr><td>커넥션 수</td><td>{m.get("connections", {}).get("avg", 0)}</td>
        <td>{conn_max}</td><td>{_status(conn_max, 150, 190)}</td></tr>
    <tr><td>TPS</td><td>{m.get("tps", {}).get("avg", 0):,}</td>
        <td>{m.get("tps", {}).get("max", 0):,}</td><td></td></tr>
    <tr><td>버퍼히트율</td><td>{m.get("buffer_hit_ratio", {}).get("avg", 0):.1f}%</td>
        <td></td><td></td></tr>
    """

    # Incidents
    incidents = report.get("incidents", [])
    crit_count = sum(1 for i in incidents if i.get("severity") == "critical")
    warn_count = sum(1 for i in incidents if i.get("severity") == "warning")
    resolved = sum(1 for i in incidents if i.get("status") == "resolved")
    inc_total = report.get("incident_count", 0)

    inc_rows = ""
    for inc in incidents[:10]:
        sev = inc.get("severity", "").upper()
        color = "#ef4444" if sev == "CRITICAL" else "#f59e0b" if sev == "WARNING" else "#94a3b8"
        inc_rows += f'<tr><td style="color:{color}">[{sev}]</td><td>{inc.get("detected_at", "")[:16]}</td><td>{inc.get("title", "")}</td></tr>\n'

    # Slow queries
    sq_rows = ""
    for q in report.get("slow_queries", [])[:10]:
        query_text = q.get("query", "")[:120]
        sq_rows += f"""
        <tr>
            <td>#{q.get("rank", 0)}</td>
            <td><code>{query_text}</code></td>
            <td>{q.get("mean_exec_time_ms", 0):.0f}ms</td>
            <td>{q.get("calls", 0):,}회</td>
            <td>{q.get("total_exec_time_ms", 0) / 1000:.1f}초</td>
        </tr>"""

    # Schema changes
    sc_rows = ""
    for sc in report.get("schema_changes", [])[:10]:
        sc_rows += f"<tr><td>[{sc.get('change_type', '')}]</td><td>{sc.get('object_name', '')}</td><td>{sc.get('detected_at', '')[:16]}</td></tr>\n"

    ai_analysis = report.get("ai_analysis", "").replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Noto Sans KR', sans-serif; color: #1e293b; padding: 40px; font-size: 11px; line-height: 1.6; }}
  h1 {{ font-size: 20px; color: #0ea5e9; margin-bottom: 4px; }}
  h2 {{ font-size: 14px; color: #334155; margin: 20px 0 8px; border-bottom: 2px solid #0ea5e9; padding-bottom: 4px; }}
  .meta {{ color: #64748b; font-size: 10px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px; }}
  th {{ background: #f1f5f9; text-align: left; padding: 6px 8px; font-weight: 500; font-size: 10px; border-bottom: 1px solid #cbd5e1; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; }}
  code {{ background: #f1f5f9; padding: 1px 4px; border-radius: 2px; font-size: 9px; word-break: break-all; }}
  .ai-box {{ background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 12px; margin: 8px 0; }}
  .footer {{ margin-top: 30px; text-align: center; color: #94a3b8; font-size: 9px; }}
</style>
</head>
<body>

<h1>NeuralDB {p} DBA 리포트</h1>
<div class="meta">
  인스턴스: <strong>{report.get("instance_name", "")}</strong> |
  기간: {report.get("start", "")[:10]} ~ {report.get("end", "")[:10]} |
  생성: {report.get("generated_at", "")[:19]}
</div>

<h2>1. 핵심 지표 요약</h2>
<table>
  <tr><th>지표</th><th>평균</th><th>최대</th><th>상태</th></tr>
  {metrics_rows}
</table>

<h2>2. 인시던트 요약</h2>
<p>총 <strong>{inc_total}</strong>건 (Critical {crit_count}, Warning {warn_count}) | 해결률: {resolved}/{inc_total}</p>
<table>
  <tr><th>심각도</th><th>시각</th><th>제목</th></tr>
  {inc_rows if inc_rows else '<tr><td colspan="3">인시던트 없음</td></tr>'}
</table>

<h2>3. Slow Query Top {len(report.get("slow_queries", []))}</h2>
<table>
  <tr><th>#</th><th>SQL</th><th>평균</th><th>호출</th><th>총 소요</th></tr>
  {sq_rows if sq_rows else '<tr><td colspan="5">Slow Query 없음</td></tr>'}
</table>

<h2>4. 스키마 변경</h2>
<p>{report.get("schema_changes_count", 0)}건의 DDL 변경</p>
<table>
  <tr><th>유형</th><th>대상</th><th>시각</th></tr>
  {sc_rows if sc_rows else '<tr><td colspan="3">변경 없음</td></tr>'}
</table>

<h2>5. AI 분석 요약</h2>
<div class="ai-box">{ai_analysis or "분석 데이터 없음"}</div>

<div class="footer">
  Generated by NeuralDB | {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</div>

</body>
</html>"""

    return html


def _html_to_simple_pdf(html: str, report: dict) -> bytes:
    """Fallback: generate a simple text-based PDF using fpdf2."""
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Use built-in font (no Korean support, but functional)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"NeuralDB DBA Report - {report.get('instance_name', '')}", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0,
            6,
            f"Period: {report.get('period', '')} | {report.get('start', '')[:10]} ~ {report.get('end', '')[:10]}",
            ln=True,
        )
        pdf.ln(5)

        # Metrics
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "1. Metrics Summary", ln=True)
        pdf.set_font("Helvetica", "", 9)
        m = report.get("metrics_summary", {})
        for key in ["cpu", "memory", "connections", "tps"]:
            vals = m.get(key, {})
            pdf.cell(0, 5, f"  {key}: avg={vals.get('avg', 0)}, max={vals.get('max', 0)}", ln=True)

        # Incidents
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"2. Incidents: {report.get('incident_count', 0)}", ln=True)

        # Slow queries
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"3. Slow Queries: {len(report.get('slow_queries', []))}", ln=True)
        pdf.set_font("Helvetica", "", 8)
        for q in report.get("slow_queries", [])[:10]:
            pdf.cell(
                0,
                4,
                f"  #{q.get('rank', 0)} {q.get('query', '')[:80]}... - {q.get('mean_exec_time_ms', 0):.0f}ms x {q.get('calls', 0)}",
                ln=True,
            )

        # AI analysis
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "5. AI Analysis", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for line in (report.get("ai_analysis", "") or "N/A").split("\n")[:10]:
            pdf.cell(0, 5, f"  {line[:100]}", ln=True)

        return pdf.output()
    except ImportError:
        # Ultimate fallback: return HTML bytes
        return html.encode("utf-8")
