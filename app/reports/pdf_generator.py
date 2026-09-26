import io

from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from app.reports.base_generator import ReportGenerator


class PDFGenerator(ReportGenerator):
    """Generate a drift summary report in PDF format."""

    def generate(self, data: dict) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        title = data.get("title", "Drift Summary Report")
        summary = data.get("summary", "")
        details = data.get("details", [])

        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 18))

        if summary:
            story.append(Paragraph(summary, styles["BodyText"]))
            story.append(Spacer(1, 12))

        for item in details:
            story.append(Paragraph(str(item), styles["BodyText"]))
            story.append(Spacer(1, 8))

        doc.build(story)
        return buffer.getvalue()
