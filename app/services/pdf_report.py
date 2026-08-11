"""PDF rendering for spec-005 — reportlab (wheel-installable everywhere; the
WeasyPrint option from the spec draft needs GTK system libs, which breaks the
run-on-host rule on Windows and adds container weight; deviation recorded in
the spec)."""

from datetime import datetime
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PRIMARY = colors.HexColor("#1976d2")
ACCENT = colors.HexColor("#ff5722")
GREY = colors.HexColor("#5f6368")


def _thin_labels(labels: list[str], max_labels: int = 26) -> list[str]:
    """Blank out crowded category labels on long ranges (bars keep their values)."""
    if len(labels) <= max_labels:
        return labels
    step = -(-len(labels) // max_labels)
    return [label if i % step == 0 else "" for i, label in enumerate(labels)]


def _fmt_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def _weekday_pt(iso: str) -> str:
    names = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    return names[datetime.strptime(iso, "%Y-%m-%d").weekday()]


def _bar_chart(values, labels, width=460, height=150, highlight_max=True):
    drawing = Drawing(width, height + 20)
    chart = VerticalBarChart()
    chart.x, chart.y = 30, 20
    chart.width, chart.height = width - 40, height - 10
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 6
    chart.categoryAxis.labels.angle = 90 if len(labels) > 16 else 0
    chart.categoryAxis.labels.boxAnchor = "e" if len(labels) > 16 else "n"
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 6
    chart.bars[0].fillColor = PRIMARY
    chart.bars[0].strokeColor = None
    if highlight_max and values and max(values) > 0:
        chart.bars[(0, values.index(max(values)))].fillColor = ACCENT
    drawing.add(chart)
    return drawing


def _kpi_table(report: dict) -> Table:
    totals = report["totals"]
    busiest_day = report["busiest_day"]
    busiest_hour = report["busiest_hour"]
    cells = [
        ("Passagens", f"{totals['passages']:,}".replace(",", ".")),
        ("Visitas estimadas", f"{totals['visits']:,}".replace(",", ".")),
        ("Média diária (passagens)", str(report["daily_average"])),
        ("Dias com movimento", f"{report['open_days']} de {report['days']}"),
        (
            "Dia mais movimentado",
            f"{_fmt_date(busiest_day['date'])} ({busiest_day['count']} passagens)"
            if busiest_day and busiest_day["count"]
            else "—",
        ),
        (
            "Horário de pico",
            f"{busiest_hour['hour']:02d}:00 ({busiest_hour['count']} passagens no período)"
            if busiest_hour["count"]
            else "—",
        ),
    ]
    data = [
        [label for label, _ in cells[:3]],
        [value for _, value in cells[:3]],
        [label for label, _ in cells[3:]],
        [value for _, value in cells[3:]],
    ]
    table = Table(data, colWidths=[160] * 3)
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 2), (-1, 2), 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
                ("TEXTCOLOR", (0, 2), (-1, 2), GREY),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 12),
                ("FONTSIZE", (0, 3), (-1, 3), 12),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 2), (-1, 2), 4),
            ]
        )
    )
    return table


def build_pdf(report: dict) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitlePT", parent=styles["Title"], fontSize=16, spaceAfter=2, textColor=PRIMARY
    )
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=9, textColor=GREY)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceBefore=14)

    generated = datetime.now().strftime("%d/%m/%Y %H:%M")
    period = f"{_fmt_date(report['start'])} a {_fmt_date(report['end'])}"

    story = [
        Paragraph("Contador de Pessoas — NCE/UFRJ", title_style),
        Paragraph(
            f"Relatório de passagens — {report['room']['name']} · {period} · gerado em {generated}",
            sub_style,
        ),
        Spacer(1, 8 * mm),
        _kpi_table(report),
        Paragraph("Passagens por dia", h2),
        _bar_chart(
            [d["count"] for d in report["per_day"]],
            _thin_labels([_fmt_date(d["date"])[:5] for d in report["per_day"]]),
        ),
        Paragraph("Distribuição por horário (total no período)", h2),
        _bar_chart(
            [h["count"] for h in report["hourly_profile"]],
            [f"{h['hour']:02d}h" for h in report["hourly_profile"]],
            height=120,
        ),
        Paragraph("Detalhamento diário", h2),
    ]

    day_rows = [["Data", "Dia da semana", "Passagens", "Visitas estimadas"]]
    for d in report["per_day"]:
        day_rows.append(
            [
                _fmt_date(d["date"]),
                _weekday_pt(d["date"]),
                str(d["count"]),
                str(-(-d["count"] // 2)),
            ]
        )
    day_table = LongTable(day_rows, colWidths=[90, 110, 90, 110], repeatRows=1)
    day_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, GREY),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(day_table)

    quality = report["data_quality"]
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Nota de qualidade dos dados: "
            + (
                f"{quality['gap_jumps']} janela(s) de perda de mensagens no período, "
                f"~{quality['estimated_missed']} passagem(ns) não registrada(s) "
                "(estimado pelo contador do sensor)."
                if quality["gap_jumps"]
                else "nenhuma perda de mensagens detectada no período."
            )
            + " Visitas estimadas = passagens ÷ 2 (entrada + saída).",
            sub_style,
        )
    )

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(20 * mm, 12 * mm, "Contador de Pessoas — Biblioteca NCE/UFRJ")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Relatório de passagens — {report['room']['name']}",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
