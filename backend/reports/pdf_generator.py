from __future__ import annotations

import httpx
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
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


def _fetch_url_bytes(url: str) -> bytes | None:
    try:
        if url.startswith("file://") or url.startswith("FILE://"):
            path = url.split("://", 1)[1]
            with open(path, "rb") as fh:
                return fh.read()
        r = httpx.get(url, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _get_facility_images(unit_id: str) -> list[tuple[str, str]]:
    """
    Return (caption, public_url) pairs for fal.ai-generated facility images.
    Reads from the iris_client image store for the facility that owns this unit.
    """
    try:
        unit = next(
            (u for u in iris_client.units.values() if u.unit_id == unit_id),
            None,
        )
        if not unit:
            return []
        images = iris_client.list_images_for_facility(unit.facility_id)
        results = []
        for img in images:
            if img.public_url:
                caption = img.description or img.area_id or "Facility Image"
                results.append((caption, img.public_url))
        return results
    except Exception:
        return []


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

    # ---- Floor plan (before / after) ----
    try:
        model = iris_client.get_model(scan.unit_id)
        sg = model.scene_graph_json
        before_url = sg.get("floor_plan_before_url") or sg.get("floor_plan_url")
        after_url  = sg.get("floor_plan_url") if sg.get("optimized") else None
    except Exception:
        before_url = after_url = None

    def _draw_plan_image(label: str, img_bytes: bytes, cur_y: float) -> float:
        img_w = PAGE_W - 2 * MARGIN
        img_h = 3.2 * inch
        if cur_y - img_h - 36 < MARGIN:
            pdf.showPage()
            cur_y = PAGE_H - MARGIN
        pdf.setFillColor(colors.HexColor("#f0f4f8"))
        pdf.rect(MARGIN - 4, cur_y - img_h - 4, img_w + 8, img_h + 24, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#1a3c5e"))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(MARGIN, cur_y, label)
        cur_y -= 16
        pdf.drawImage(ImageReader(BytesIO(img_bytes)), MARGIN, cur_y - img_h, width=img_w, height=img_h)
        return cur_y - img_h - 20

    if before_url:
        b = _fetch_url_bytes(before_url)
        if b:
            y = _draw_plan_image("Current Layout", b, y)

    if after_url and after_url != before_url:
        b = _fetch_url_bytes(after_url)
        if b:
            y = _draw_plan_image("Optimized Layout", b, y)

    # ---- fal.ai Facility Images ----
    fal_images = _get_facility_images(scan.unit_id)
    if fal_images:
        if y < MARGIN + 80:
            pdf.showPage()
            y = PAGE_H - MARGIN
        pdf.setFillColor(colors.HexColor("#1a3c5e"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(MARGIN, y, "AI-Generated Facility Images")
        y -= 20

        img_w = (PAGE_W - 2 * MARGIN - 12) / 2
        img_h = 2.0 * inch
        col = 0
        row_start_y = y

        for caption, url in fal_images[:6]:  # cap at 6 images
            b = _fetch_url_bytes(url)
            if not b:
                continue
            if col == 2:
                col = 0
                row_start_y -= img_h + 30
                if row_start_y - img_h < MARGIN:
                    pdf.showPage()
                    row_start_y = PAGE_H - MARGIN - 20

            x_pos = MARGIN + col * (img_w + 12)
            try:
                pdf.drawImage(ImageReader(BytesIO(b)), x_pos, row_start_y - img_h, width=img_w, height=img_h)
                pdf.setFillColor(colors.HexColor("#555555"))
                pdf.setFont("Helvetica-Oblique", 8)
                pdf.drawString(x_pos, row_start_y - img_h - 10, caption[:55])
            except Exception:
                pass
            col += 1

        y = row_start_y - img_h - 30
        y -= 10

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
