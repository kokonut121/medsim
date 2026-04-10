from __future__ import annotations

import httpx
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from backend.db.iris_client import iris_client
from backend.models import Scan

PAGE_W, PAGE_H = letter
MARGIN = 72


def _fetch_floor_plan(unit_id: str) -> bytes | None:
    """Pull the floor plan image from the scene_graph_json stored on the model."""
    try:
        model = iris_client.get_model(unit_id)
        url = model.scene_graph_json.get("floor_plan_url")
        if not url:
            return None
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception:
        return None


def build_pdf(scan: Scan) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"MedSentinel Safety Report — {scan.scan_id}")

    # ---- Header ----
    pdf.setFillColor(colors.HexColor("#1a3c5e"))
    pdf.rect(0, PAGE_H - 60, PAGE_W, 60, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(MARGIN, PAGE_H - 38, "MedSentinel Safety Report")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(MARGIN, PAGE_H - 52, f"Unit: {scan.unit_id}  |  Scan: {scan.scan_id}  |  Status: {scan.status}")

    y = PAGE_H - 80

    # ---- Floor plan ----
    floor_plan_bytes = _fetch_floor_plan(scan.unit_id)
    if floor_plan_bytes:
        try:
            img_buffer = BytesIO(floor_plan_bytes)
            img_w = PAGE_W - 2 * MARGIN
            img_h = 3 * inch
            pdf.setFillColor(colors.HexColor("#f0f4f8"))
            pdf.rect(MARGIN - 4, y - img_h - 4, img_w + 8, img_h + 24, fill=1, stroke=0)
            pdf.setFillColor(colors.HexColor("#1a3c5e"))
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(MARGIN, y, "Facility Floor Plan")
            y -= 16
            pdf.drawInlineImage(img_buffer, MARGIN, y - img_h, width=img_w, height=img_h)
            y -= img_h + 20
        except Exception:
            pass  # skip floor plan if image can't be rendered

    # ---- Domain summary ----
    pdf.setFillColor(colors.HexColor("#1a3c5e"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN, y, "Domain Summary")
    y -= 18

    severity_colors = {
        "CRITICAL": colors.HexColor("#c0392b"),
        "HIGH": colors.HexColor("#e67e22"),
        "ADVISORY": colors.HexColor("#2980b9"),
    }

    for domain, status in scan.domain_statuses.items():
        pdf.setFillColor(colors.HexColor("#333333"))
        pdf.setFont("Helvetica", 10)
        pdf.drawString(MARGIN, y, f"{domain}  —  {status.finding_count} finding(s)  |  {status.status}")
        y -= 14
        if y < MARGIN + 40:
            pdf.showPage()
            y = PAGE_H - MARGIN

    y -= 10

    # ---- Findings ----
    pdf.setFillColor(colors.HexColor("#1a3c5e"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN, y, "Findings")
    y -= 18

    for finding in scan.findings:
        if y < MARGIN + 60:
            pdf.showPage()
            y = PAGE_H - MARGIN

        sev_color = severity_colors.get(finding.severity, colors.grey)
        pdf.setFillColor(sev_color)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(MARGIN, y, f"[{finding.severity}]  {finding.domain}  —  Room {finding.room_id}")
        y -= 13

        pdf.setFillColor(colors.HexColor("#222222"))
        pdf.setFont("Helvetica", 9)
        # Wrap label text at ~90 chars
        label = finding.label_text
        while label:
            pdf.drawString(MARGIN + 12, y, label[:100])
            label = label[100:]
            y -= 12

        pdf.setFillColor(colors.HexColor("#555555"))
        pdf.setFont("Helvetica-Oblique", 8)
        rec = finding.recommendation
        while rec:
            pdf.drawString(MARGIN + 12, y, f"→ {rec[:95]}")
            rec = rec[95:]
            y -= 11

        y -= 6

    pdf.save()
    return buffer.getvalue()
