"""PDF generation using WeasyPrint."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

from ..models.regulatory import ComplianceReport
from ..models.allergen import AllergenReport
from ..models.voc import VOCReport
from ..models.fse import FSEReport


# Template directory
TEMPLATE_DIR = Path(__file__).parent / "templates"


class PDFGenerator:
    """Generate PDF documents from compliance data."""

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        company_name: str = "Fragrance Company",
        company_logo: Optional[Path] = None,
    ):
        """Initialize the PDF generator.

        Args:
            template_dir: Directory containing Jinja2 templates.
            company_name: Company name for certificates.
            company_logo: Path to company logo image.
        """
        self.template_dir = template_dir or TEMPLATE_DIR
        self.company_name = company_name
        self.company_logo = company_logo

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )

        # Add custom filters
        self.env.filters["format_percent"] = lambda x: f"{x:.4f}%" if x else "N/A"
        self.env.filters["format_date"] = lambda x: x.strftime("%B %d, %Y") if x else ""

    def _render_template(self, template_name: str, context: dict) -> str:
        """Render a Jinja2 template to HTML.

        Args:
            template_name: Name of template file.
            context: Template context variables.

        Returns:
            Rendered HTML string.
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def _generate_pdf(self, html_content: str, output_path: Path) -> Path:
        """Generate PDF from HTML content.

        Args:
            html_content: Rendered HTML string.
            output_path: Output file path.

        Returns:
            Path to generated PDF.
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError("WeasyPrint is not installed. Run: pip install weasyprint")

        # Load stylesheet
        css_path = self.template_dir / "styles.css"
        stylesheets = []
        if css_path.exists():
            stylesheets.append(CSS(filename=str(css_path)))

        # Generate PDF
        html = HTML(string=html_content)
        html.write_pdf(output_path, stylesheets=stylesheets)

        return output_path

    def generate_ifra_certificate(
        self,
        report: ComplianceReport,
        output_path: Path,
        signatory_name: Optional[str] = None,
        signatory_title: Optional[str] = None,
    ) -> Path:
        """Generate IFRA Certificate of Conformity.

        Args:
            report: Compliance report data.
            output_path: Output file path.
            signatory_name: Name of person signing certificate.
            signatory_title: Title of signatory.

        Returns:
            Path to generated PDF.
        """
        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "signatory_name": signatory_name or "Quality Assurance Manager",
            "signatory_title": signatory_title or "Quality Assurance",
            "generated_date": datetime.now(),
            "document_type": "IFRA Certificate of Conformity",
        }

        html = self._render_template("ifra_certificate.html", context)
        return self._generate_pdf(html, output_path)

    def generate_allergen_statement(
        self,
        report: AllergenReport,
        output_path: Path,
    ) -> Path:
        """Generate Allergen Declaration Statement.

        Args:
            report: Allergen report data.
            output_path: Output file path.

        Returns:
            Path to generated PDF.
        """
        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "Allergen Declaration",
        }

        html = self._render_template("allergen_statement.html", context)
        return self._generate_pdf(html, output_path)

    def generate_voc_statement(
        self,
        report: VOCReport,
        output_path: Path,
    ) -> Path:
        """Generate VOC Compliance Statement.

        Args:
            report: VOC report data.
            output_path: Output file path.

        Returns:
            Path to generated PDF.
        """
        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "VOC Compliance Statement",
        }

        html = self._render_template("voc_statement.html", context)
        return self._generate_pdf(html, output_path)

    def generate_fse(
        self,
        report: FSEReport,
        output_path: Path,
    ) -> Path:
        """Generate Fragrance Safety Evaluation document.

        Args:
            report: FSE report data.
            output_path: Output file path.

        Returns:
            Path to generated PDF.
        """
        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "Fragrance Safety Evaluation",
        }

        html = self._render_template("fse_report.html", context)
        return self._generate_pdf(html, output_path)

    def generate_html_preview(
        self,
        template_name: str,
        context: dict,
    ) -> str:
        """Generate HTML preview without PDF conversion.

        Args:
            template_name: Name of template file.
            context: Template context variables.

        Returns:
            Rendered HTML string.
        """
        return self._render_template(template_name, context)
