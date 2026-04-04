from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.models import Scan


def build_pdf(scan: Scan) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"MedSentinel Report {scan.scan_id}")
    pdf.drawString(72, 750, f"MedSentinel report for unit {scan.unit_id}")
    pdf.drawString(72, 732, f"Scan status: {scan.status}")
    y = 700
    for finding in scan.findings[:12]:
        pdf.drawString(72, y, f"{finding.domain} | {finding.severity} | {finding.label_text[:80]}")
        y -= 18
        if y < 72:
            pdf.showPage()
            y = 750
    pdf.save()
    return buffer.getvalue()

