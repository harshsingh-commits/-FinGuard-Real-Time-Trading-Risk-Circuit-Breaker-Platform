"""Audit timeline and PDF export."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def root_cause_summary(incident: dict) -> str:
    reason = incident.get("reason", "threshold breach")
    score = incident.get("risk_score", 0)
    return f"Incident caused by {reason}. Composite risk score reached {score}. Execution governance was engaged."


def export_audit_pdf(incident: dict, timeline: list[dict]) -> bytes:
    buffer = BytesIO()
    document = canvas.Canvas(buffer, pagesize=letter)
    document.setTitle("FinGuard Audit Report")
    document.drawString(54, 750, "FinGuard Audit Report")
    document.drawString(54, 730, root_cause_summary(incident))
    y = 700
    for item in timeline:
        document.drawString(54, y, f"{item.get('timestamp', '')} | {item.get('event', 'state transition')}")
        y -= 18
        if y < 54:
            document.showPage()
            y = 750
    document.save()
    return buffer.getvalue()