import csv
import io

from app.reports.base_generator import ReportGenerator


class CSVGenerator(ReportGenerator):
    """Generate a drift detail report in CSV format."""

    def generate(self, data: dict) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)

        rows = data.get("rows", [])
        headers = data.get("headers", [])

        if headers:
            writer.writerow(headers)

        for row in rows:
            writer.writerow(row)

        return output.getvalue().encode("utf-8")
