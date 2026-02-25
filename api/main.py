"""FastAPI application for regulatory compliance API."""

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.models.regulatory import Market, ProductType
from src.services.compliance_engine import ComplianceEngine
from src.documents.pdf_generator import PDFGenerator
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData


app = FastAPI(
    title="Smell-Reg API",
    description="Fragrance Regulatory Compliance API",
    version="0.1.0",
)

# Initialize services
engine = ComplianceEngine()
pdf_generator = PDFGenerator()


# Request/Response Models
class IngredientInput(BaseModel):
    """Input model for a formula ingredient."""
    cas_number: str
    name: str
    percentage: float = Field(gt=0, le=100)


class FormulaInput(BaseModel):
    """Input model for a formula."""
    name: str
    ingredients: list[IngredientInput]


class ComplianceCheckRequest(BaseModel):
    """Request model for full compliance check."""
    formula: FormulaInput
    product_type: str
    markets: list[str]
    fragrance_concentration: float = Field(default=100.0, gt=0, le=100)
    is_leave_on: bool = True


class IFRACheckRequest(BaseModel):
    """Request model for IFRA compliance check."""
    formula: FormulaInput
    product_type: str
    fragrance_concentration: float = Field(default=100.0, gt=0, le=100)


class AllergenCheckRequest(BaseModel):
    """Request model for allergen check."""
    formula: FormulaInput
    markets: list[str]
    fragrance_concentration: float = Field(default=100.0, gt=0, le=100)
    is_leave_on: bool = True


class VOCCheckRequest(BaseModel):
    """Request model for VOC check."""
    formula: FormulaInput
    product_type: str
    markets: list[str]


class DocumentRequest(BaseModel):
    """Request model for document generation."""
    formula: FormulaInput
    product_type: str
    markets: list[str] = []
    fragrance_concentration: float = Field(default=100.0, gt=0, le=100)
    is_leave_on: bool = True
    signatory_name: Optional[str] = None
    signatory_title: Optional[str] = None
    assessor: Optional[str] = None
    intended_use: Optional[str] = None


# Helper functions
def _to_formula_data(formula_input: FormulaInput) -> FormulaData:
    """Convert FormulaInput to FormulaData."""
    return FormulaData(
        name=formula_input.name,
        ingredients=[
            FormulaIngredientData(
                cas_number=ing.cas_number,
                name=ing.name,
                percentage=ing.percentage,
            )
            for ing in formula_input.ingredients
        ],
    )


def _parse_markets(market_strs: list[str]) -> list[Market]:
    """Parse market strings to Market enums."""
    markets = []
    for m in market_strs:
        try:
            markets.append(Market(m.lower()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid market: {m}")
    return markets


def _parse_product_type(product_type_str: str) -> ProductType:
    """Parse product type string to ProductType enum."""
    try:
        return ProductType(product_type_str.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid product type: {product_type_str}")


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Smell-Reg API",
        "version": "0.1.0",
        "description": "Fragrance Regulatory Compliance API",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/compliance/check")
async def check_compliance(request: ComplianceCheckRequest):
    """Run full compliance check across all services."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)
    markets = _parse_markets(request.markets)

    report = engine.check_compliance(
        formula=formula,
        product_type=product_type,
        markets=markets,
        fragrance_concentration=request.fragrance_concentration,
        is_leave_on=request.is_leave_on,
    )

    return report.to_dict()


@app.post("/api/compliance/ifra")
async def check_ifra(request: IFRACheckRequest):
    """Check IFRA compliance only."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)

    result = engine.check_ifra(
        formula=formula,
        product_type=product_type,
        fragrance_concentration=request.fragrance_concentration,
    )

    return {
        "is_compliant": result.is_compliant,
        "violations": [v.to_dict() for v in result.violations],
        "warnings": [w.to_dict() for w in result.warnings],
        "compliant_ingredients": result.compliant_ingredients,
        "certificate_number": result.certificate_number,
    }


@app.post("/api/compliance/allergens")
async def check_allergens(request: AllergenCheckRequest):
    """Check allergen content and disclosure requirements."""
    formula = _to_formula_data(request.formula)
    markets = _parse_markets(request.markets)

    report = engine.check_allergens(
        formula=formula,
        markets=markets,
        fragrance_concentration=request.fragrance_concentration,
        is_leave_on=request.is_leave_on,
    )

    return report.to_dict()


@app.post("/api/compliance/voc")
async def check_voc(request: VOCCheckRequest):
    """Check VOC compliance."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)
    markets = _parse_markets(request.markets)

    report = engine.check_voc(
        formula=formula,
        product_type=product_type,
        markets=markets,
    )

    return report.to_dict()


@app.post("/api/documents/ifra-certificate")
async def generate_ifra_certificate(request: DocumentRequest):
    """Generate IFRA Certificate of Conformity PDF."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)
    markets = _parse_markets(request.markets) if request.markets else [Market.US]

    # Run compliance check first
    report = engine.check_compliance(
        formula=formula,
        product_type=product_type,
        markets=markets,
        fragrance_concentration=request.fragrance_concentration,
        is_leave_on=request.is_leave_on,
    )

    # Generate PDF
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        output_path = Path(tmp.name)

    pdf_generator.generate_ifra_certificate(
        report=report,
        output_path=output_path,
        signatory_name=request.signatory_name,
        signatory_title=request.signatory_title,
    )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"IFRA_Certificate_{formula.name}_{datetime.now().strftime('%Y%m%d')}.pdf",
    )


@app.post("/api/documents/allergen-statement")
async def generate_allergen_statement(request: DocumentRequest):
    """Generate Allergen Declaration Statement PDF."""
    formula = _to_formula_data(request.formula)
    markets = _parse_markets(request.markets) if request.markets else [Market.EU]

    # Run allergen check
    report = engine.check_allergens(
        formula=formula,
        markets=markets,
        fragrance_concentration=request.fragrance_concentration,
        is_leave_on=request.is_leave_on,
    )

    # Generate PDF
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        output_path = Path(tmp.name)

    pdf_generator.generate_allergen_statement(
        report=report,
        output_path=output_path,
    )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"Allergen_Statement_{formula.name}_{datetime.now().strftime('%Y%m%d')}.pdf",
    )


@app.post("/api/documents/voc-statement")
async def generate_voc_statement(request: DocumentRequest):
    """Generate VOC Compliance Statement PDF."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)
    markets = _parse_markets(request.markets) if request.markets else [Market.US]

    # Run VOC check
    report = engine.check_voc(
        formula=formula,
        product_type=product_type,
        markets=markets,
    )

    # Generate PDF
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        output_path = Path(tmp.name)

    pdf_generator.generate_voc_statement(
        report=report,
        output_path=output_path,
    )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"VOC_Statement_{formula.name}_{datetime.now().strftime('%Y%m%d')}.pdf",
    )


@app.post("/api/documents/fse")
async def generate_fse(request: DocumentRequest):
    """Generate Fragrance Safety Evaluation PDF."""
    formula = _to_formula_data(request.formula)
    product_type = _parse_product_type(request.product_type)

    # Generate FSE report
    report = engine.generate_fse(
        formula=formula,
        product_type=product_type,
        fragrance_concentration=request.fragrance_concentration,
        intended_use=request.intended_use or "",
        assessor=request.assessor,
    )

    # Generate PDF
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        output_path = Path(tmp.name)

    pdf_generator.generate_fse(
        report=report,
        output_path=output_path,
    )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"FSE_{formula.name}_{datetime.now().strftime('%Y%m%d')}.pdf",
    )


@app.post("/api/formulas/import")
async def import_formula(formula: FormulaInput):
    """Import a formula for compliance checking.

    This endpoint validates the formula structure and returns
    a summary of the formula ready for compliance checks.
    """
    formula_data = _to_formula_data(formula)

    return {
        "name": formula_data.name,
        "ingredient_count": len(formula_data.ingredients),
        "total_percentage": sum(ing.percentage for ing in formula_data.ingredients),
        "ingredients": [
            {
                "cas_number": ing.cas_number,
                "name": ing.name,
                "percentage": ing.percentage,
            }
            for ing in formula_data.ingredients
        ],
    }


# Reference data endpoints
@app.get("/api/reference/markets")
async def get_markets():
    """Get list of supported markets."""
    return [{"value": m.value, "name": m.name} for m in Market]


@app.get("/api/reference/product-types")
async def get_product_types():
    """Get list of supported product types."""
    return [{"value": pt.value, "name": pt.name} for pt in ProductType]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
