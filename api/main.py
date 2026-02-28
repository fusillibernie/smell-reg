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
from src.services.materials_service import MaterialsService
from src.services.formula_library import FormulaLibrary
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
materials_service = MaterialsService()
formula_library = FormulaLibrary()


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


# Materials search endpoints
@app.get("/api/materials/search")
async def search_materials(q: str, limit: int = 20):
    """Search raw materials by name, CAS number, or INCI name.

    Args:
        q: Search query.
        limit: Maximum results (default 20).

    Returns:
        List of matching materials.
    """
    results = materials_service.search(q, limit=limit)
    return [m.to_dict() for m in results]


@app.get("/api/materials/{cas_number}")
async def get_material(cas_number: str):
    """Get a material by CAS number.

    Args:
        cas_number: CAS registry number.

    Returns:
        Material details or 404.
    """
    material = materials_service.get_by_cas(cas_number)
    if not material:
        raise HTTPException(status_code=404, detail=f"Material not found: {cas_number}")
    return material.to_dict()


@app.get("/api/materials/odor/{odor_family}")
async def get_materials_by_odor(odor_family: str):
    """Get materials by odor family.

    Args:
        odor_family: Odor family (e.g., floral, woody, citrus).

    Returns:
        List of materials in that odor family.
    """
    results = materials_service.search_by_odor_family(odor_family)
    return [m.to_dict() for m in results]


# Formula library endpoints
class FormulaLibraryInput(BaseModel):
    """Input model for saving a formula to the library."""
    name: str
    ingredients: list[IngredientInput]
    description: Optional[str] = None
    tags: list[str] = []


@app.get("/api/library/formulas")
async def list_formulas():
    """List all formulas in the library."""
    formulas = formula_library.list_all()
    return [f.to_dict() for f in formulas]


@app.get("/api/library/formulas/{formula_id}")
async def get_formula(formula_id: str):
    """Get a formula by ID.

    Args:
        formula_id: Formula ID.

    Returns:
        Formula details or 404.
    """
    formula = formula_library.get(formula_id)
    if not formula:
        raise HTTPException(status_code=404, detail=f"Formula not found: {formula_id}")
    return formula.to_dict()


@app.post("/api/library/formulas")
async def save_formula(formula_input: FormulaLibraryInput):
    """Save a formula to the library.

    Args:
        formula_input: Formula data.

    Returns:
        Saved formula with ID.
    """
    ingredients = [
        {
            "cas_number": ing.cas_number,
            "name": ing.name,
            "percentage": ing.percentage,
        }
        for ing in formula_input.ingredients
    ]

    formula = formula_library.save(
        name=formula_input.name,
        ingredients=ingredients,
        description=formula_input.description,
        tags=formula_input.tags,
    )

    return formula.to_dict()


@app.put("/api/library/formulas/{formula_id}")
async def update_formula(formula_id: str, formula_input: FormulaLibraryInput):
    """Update an existing formula.

    Args:
        formula_id: Formula ID.
        formula_input: Updated formula data.

    Returns:
        Updated formula.
    """
    existing = formula_library.get(formula_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Formula not found: {formula_id}")

    ingredients = [
        {
            "cas_number": ing.cas_number,
            "name": ing.name,
            "percentage": ing.percentage,
        }
        for ing in formula_input.ingredients
    ]

    formula = formula_library.save(
        name=formula_input.name,
        ingredients=ingredients,
        description=formula_input.description,
        tags=formula_input.tags,
        formula_id=formula_id,
    )

    return formula.to_dict()


@app.delete("/api/library/formulas/{formula_id}")
async def delete_formula(formula_id: str):
    """Delete a formula from the library.

    Args:
        formula_id: Formula ID.

    Returns:
        Success message.
    """
    if not formula_library.delete(formula_id):
        raise HTTPException(status_code=404, detail=f"Formula not found: {formula_id}")
    return {"message": "Formula deleted"}


@app.post("/api/library/formulas/{formula_id}/duplicate")
async def duplicate_formula(formula_id: str, new_name: Optional[str] = None):
    """Duplicate a formula.

    Args:
        formula_id: Formula ID to duplicate.
        new_name: Optional name for the new formula.

    Returns:
        New formula.
    """
    formula = formula_library.duplicate(formula_id, new_name)
    if not formula:
        raise HTTPException(status_code=404, detail=f"Formula not found: {formula_id}")
    return formula.to_dict()


@app.get("/api/library/search")
async def search_formulas(q: str):
    """Search formulas by name or tags.

    Args:
        q: Search query.

    Returns:
        List of matching formulas.
    """
    results = formula_library.search(q)
    return [f.to_dict() for f in results]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
