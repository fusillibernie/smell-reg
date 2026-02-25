# Smell-Reg: Fragrance Regulatory Compliance Application

A comprehensive regulatory compliance tool for fragrance products that generates compliance certificates and safety documentation for multiple markets.

## Features

### Compliance Checks
- **IFRA Compliance** - Checks against IFRA 51st Amendment category limits
- **Allergen Detection** - EU 26/82 allergens, Canada 24/81 allergens with disclosure thresholds
- **VOC Compliance** - California CARB and Canada VOC regulations
- **Formaldehyde Donors** - Detection of formaldehyde-releasing preservatives
- **Market-Specific** - Prop 65, REACH SVHC, Canada Hotlist

### Document Generation
- IFRA Certificate of Conformity
- Allergen Declaration Statement
- VOC Compliance Statement
- Fragrance Safety Evaluation (FSE)

### Target Markets
US, EU, UK, Canada, Japan, China, Australia, Brazil

## Installation

```bash
cd C:\Users\pwong\projects\smell-reg
pip install -e .

# For development
pip install -e ".[dev]"

# For PDF generation
pip install weasyprint

# For web UI
pip install streamlit
```

## Quick Start

### Python API

```python
from src.services import ComplianceEngine
from src.integrations.aroma_lab import FormulaData, FormulaIngredientData
from src.models import Market, ProductType

# Create a formula
formula = FormulaData(
    name="My Fragrance",
    ingredients=[
        FormulaIngredientData(cas_number="64-17-5", name="Ethanol", percentage=70.0),
        FormulaIngredientData(cas_number="78-70-6", name="Linalool", percentage=15.0),
        FormulaIngredientData(cas_number="5989-27-5", name="d-Limonene", percentage=10.0),
        FormulaIngredientData(cas_number="91-64-5", name="Coumarin", percentage=5.0),
    ]
)

# Run compliance check
engine = ComplianceEngine()
report = engine.check_compliance(
    formula=formula,
    product_type=ProductType.FINE_FRAGRANCE,
    markets=[Market.US, Market.EU, Market.CA],
    fragrance_concentration=20.0,  # 20% fragrance in final product
    is_leave_on=True
)

print(f"Compliant: {report.is_compliant}")
print(f"Certificate: {report.certificate_number}")
for result in report.non_compliant_items:
    print(f"  - {result.requirement}: {result.details}")
```

### REST API

```bash
# Start the API server
uvicorn api.main:app --reload

# Check compliance
curl -X POST http://localhost:8000/api/compliance/check \
  -H "Content-Type: application/json" \
  -d '{
    "formula": {
      "name": "Test Fragrance",
      "ingredients": [
        {"cas_number": "64-17-5", "name": "Ethanol", "percentage": 70},
        {"cas_number": "78-70-6", "name": "Linalool", "percentage": 30}
      ]
    },
    "product_type": "fine_fragrance",
    "markets": ["us", "eu"],
    "fragrance_concentration": 20
  }'
```

### Web Interface

```bash
streamlit run ui/app.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/compliance/check` | POST | Full compliance check |
| `/api/compliance/ifra` | POST | IFRA-only check |
| `/api/compliance/allergens` | POST | Allergen detection |
| `/api/compliance/voc` | POST | VOC calculations |
| `/api/documents/ifra-certificate` | POST | Generate IFRA PDF |
| `/api/documents/allergen-statement` | POST | Generate allergen PDF |
| `/api/documents/voc-statement` | POST | Generate VOC PDF |
| `/api/documents/fse` | POST | Generate FSE PDF |
| `/api/reference/markets` | GET | List supported markets |
| `/api/reference/product-types` | GET | List product types |

## Regulatory Data

All regulatory data is stored in `data/regulatory/` as JSON files:

| File | Contents |
|------|----------|
| `allergens.json` | EU and Canada allergen lists with thresholds |
| `voc_limits.json` | CARB and Canada VOC limits by product category |
| `voc_ingredients.json` | VOC classification of common ingredients |
| `formaldehyde_donors.json` | Formaldehyde-releasing substances |
| `prop65.json` | California Prop 65 listed substances |
| `canada_hotlist.json` | Health Canada prohibited/restricted substances |
| `reach.json` | EU REACH SVHC and Annex XVII restrictions |
| `metadata.json` | Version tracking and update sources |

### Updating Regulatory Data

Regulatory data requires manual updates. To update:

1. Check the source URLs in `data/regulatory/metadata.json`
2. Edit the relevant JSON file with new data
3. Update `metadata.json` with new version and date
4. Add entry to `update_log` describing changes

**Recommended update frequency:**
- IFRA Standards: Quarterly (new amendments ~annually)
- EU Allergens: Monthly (watch for new annexes)
- Prop 65: Quarterly
- REACH SVHC: Monthly (new substances added periodically)
- VOC Limits: Annually

## Integration with aroma-lab

This project imports models from `C:\Users\pwong\projects\aroma-lab`:
- `IFRACategory`, `IFRARestriction`, `RestrictionType`
- `SafetyData`, `Citation`
- `Aromachemical`, `Formula`, `FormulaIngredient`

## Testing

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=src tests/
```

## Project Structure

```
smell-reg/
├── src/
│   ├── models/           # Data models
│   │   ├── regulatory.py # Market, ProductType, ComplianceResult
│   │   ├── allergen.py   # Allergen, AllergenReport
│   │   ├── voc.py        # VOCLimit, VOCCalculation
│   │   └── fse.py        # FSE endpoints and reports
│   ├── services/         # Business logic
│   │   ├── compliance_engine.py  # Main orchestrator
│   │   ├── ifra_service.py       # IFRA compliance
│   │   ├── allergen_service.py   # Allergen detection
│   │   ├── voc_service.py        # VOC calculations
│   │   ├── fse_service.py        # FSE generation
│   │   ├── market_service.py     # Prop 65, REACH, Hotlist
│   │   └── formaldehyde_service.py # Formaldehyde donors
│   ├── documents/        # PDF generation
│   │   ├── pdf_generator.py
│   │   └── templates/    # HTML/CSS templates
│   ├── data/             # Data access layer
│   └── integrations/     # aroma-lab client
├── api/                  # FastAPI application
├── ui/                   # Streamlit web interface
├── data/regulatory/      # JSON regulatory data
└── tests/
```

## Compliance Checks Performed

### IFRA (International Fragrance Association)
- Checks ingredient concentrations against category-specific limits
- Identifies prohibited substances
- Warns when approaching limits (>90% of max)
- Supports all 18 IFRA categories

### Allergens
- **EU 26 Allergens** - Original Cosmetics Regulation list
- **EU 82 Allergens** - Expanded 2023 list (EC 2023/1545)
- **Canada 24/81 Allergens** - Health Canada lists
- Applies correct thresholds: 0.001% leave-on, 0.01% rinse-off

### VOC (Volatile Organic Compounds)
- **CARB** - California Air Resources Board limits
- **Canada CEPA** - Canadian VOC regulations
- Accounts for exempt compounds (acetone, propylene glycol, etc.)

### Formaldehyde Donors
- Detects formaldehyde-releasing preservatives
- Checks against EU limits (Annex V)
- Flags labeling requirements ("contains formaldehyde")
- Identifies banned substances (bronopol in EU)

### Market-Specific
- **Prop 65** - California cancer/reproductive toxicity warnings
- **REACH** - EU SVHC notification, Annex XVII restrictions
- **Canada Hotlist** - Prohibited and restricted substances

## Known Limitations

1. **IFRA Data** - Requires aroma-lab IFRA database to be populated
2. **PDF Generation** - Requires WeasyPrint (system dependencies)
3. **Regulatory Updates** - Manual process; data may become outdated
4. **QSAR Data** - FSE currently doesn't include QSAR predictions
5. **Natural Compositions** - Doesn't auto-expand natural ingredients

## License

Internal use only.

## Support

For issues or feature requests, contact the regulatory compliance team.
