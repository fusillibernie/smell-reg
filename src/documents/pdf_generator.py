"""PDF generation using WeasyPrint."""

import json
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

# Allergen data file
ALLERGEN_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "regulatory" / "allergens.json"


def load_all_allergens() -> list:
    """Load all allergens from the database for complete listing."""
    if not ALLERGEN_DATA_FILE.exists():
        return []

    try:
        with open(ALLERGEN_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("allergens", [])
    except:
        return []


class PDFGenerator:
    """Generate PDF documents from compliance data."""

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        company_name: str = "Fragrance Company",
        company_logo: Optional[Path] = None,
    ):
        """Initialize the PDF generator."""
        self.template_dir = template_dir or TEMPLATE_DIR
        self.company_name = company_name
        self.company_logo = company_logo

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )

        # Add custom filters
        self.env.filters["format_percent"] = lambda x: f"{x:.4f}%" if x is not None else "N/A"
        self.env.filters["format_date"] = lambda x: x.strftime("%B %d, %Y") if x else ""

    def _render_template(self, template_name: str, context: dict) -> str:
        """Render a Jinja2 template to HTML."""
        template = self.env.get_template(template_name)
        return template.render(**context)

    def _generate_pdf(self, html_content: str, output_path: Path) -> Path:
        """Generate PDF from HTML content."""
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

    def _default_metadata(self) -> dict:
        """Return default metadata values."""
        return {
            "formula_code": "",
            "formula_name": "",
            "version": "1",
            "date_created": datetime.now().strftime("%Y-%m-%d"),
        }

    def generate_ifra_certificate(
        self,
        report: ComplianceReport,
        output_path: Path,
        signatory_name: Optional[str] = None,
        signatory_title: Optional[str] = None,
        metadata: Optional[dict] = None,
        max_use_levels: Optional[dict] = None,
    ) -> Path:
        """Generate IFRA Certificate of Conformity.

        Args:
            report: ComplianceReport with IFRA compliance results.
            output_path: Path to write the PDF.
            signatory_name: Name for signature block.
            signatory_title: Title for signature block.
            metadata: Formula metadata (code, name, version, date).
            max_use_levels: Dict mapping IFRA category to max use % string.
                           If not provided, uses "Not Limited" for all.
        """
        meta = self._default_metadata()
        if metadata:
            meta.update(metadata)

        # Default max use levels - should be calculated by IFRA service
        # based on the limiting ingredient in the formula
        default_levels = {
            "1": "Not Limited",
            "2": "Not Limited",
            "3": "Not Limited",
            "4": "Not Limited",
            "5A": "Not Limited",
            "5B": "Not Limited",
            "5C": "Not Limited",
            "5D": "Not Limited",
            "6": "Not Limited",
            "7A": "Not Limited",
            "7B": "Not Limited",
            "8": "Not Limited",
            "9": "Not Limited",
            "10A": "Not Limited",
            "10B": "Not Limited",
            "11A": "Not Limited",
            "11B": "Not Limited",
            "12": "Not Limited",
        }

        # Use provided levels or defaults
        max_levels = max_use_levels or default_levels

        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "signatory_name": signatory_name or "Quality Assurance Manager",
            "signatory_title": signatory_title or "Quality Assurance",
            "generated_date": datetime.now(),
            "document_type": "IFRA Certificate of Conformity",
            "metadata": meta,
            "max_levels": max_levels,
        }

        html = self._render_template("ifra_certificate.html", context)
        return self._generate_pdf(html, output_path)

    def generate_allergen_statement(
        self,
        report: AllergenReport,
        output_path: Path,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Generate Allergen Declaration Statement with ALL allergens listed."""
        meta = self._default_metadata()
        if metadata:
            meta.update(metadata)

        # Load all allergens from database
        all_allergens_data = load_all_allergens()

        # Create a map of detected allergens by CAS
        detected_map = {}
        for a in report.detected_allergens:
            detected_map[a.cas_number] = a.concentration_in_fragrance

        # Build complete allergen list with concentrations
        all_allergens = []
        for allergen in all_allergens_data:
            cas = allergen.get("cas_number", "")
            name = allergen.get("inci_name") or allergen.get("name", "")
            concentration = detected_map.get(cas, 0.0)
            all_allergens.append({
                "name": name,
                "cas_number": cas,
                "concentration": concentration,
            })

        # Sort alphabetically by name
        all_allergens.sort(key=lambda x: x["name"])

        context = {
            "report": report,
            "all_allergens": all_allergens,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "Allergen Declaration",
            "metadata": meta,
        }

        html = self._render_template("allergen_statement.html", context)
        return self._generate_pdf(html, output_path)

    def generate_voc_statement(
        self,
        report: VOCReport,
        output_path: Path,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Generate VOC Compliance Statement."""
        meta = self._default_metadata()
        if metadata:
            meta.update(metadata)

        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "VOC Compliance Statement",
            "metadata": meta,
        }

        html = self._render_template("voc_statement.html", context)
        return self._generate_pdf(html, output_path)

    def generate_fse(
        self,
        report: FSEReport,
        output_path: Path,
        metadata: Optional[dict] = None,
    ) -> Path:
        """Generate Fragrance Safety Evaluation document."""
        meta = self._default_metadata()
        if metadata:
            meta.update(metadata)

        # Set formula name in metadata if not provided
        if not meta.get("formula_code"):
            meta["formula_code"] = getattr(report, 'report_number', '') or ''

        context = {
            "report": report,
            "company_name": self.company_name,
            "company_logo": self.company_logo,
            "generated_date": datetime.now(),
            "document_type": "Fragrance Safety Evaluation",
            "metadata": meta,
        }

        html = self._render_template("fse_report.html", context)
        return self._generate_pdf(html, output_path)

    def generate_html_preview(
        self,
        template_name: str,
        context: dict,
    ) -> str:
        """Generate HTML preview without PDF conversion."""
        return self._render_template(template_name, context)
