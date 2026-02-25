"""Fragrance Safety Evaluation (FSE) data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class FSEEndpoint(Enum):
    """Toxicological endpoints for FSE assessment."""
    SKIN_SENSITIZATION = "skin_sensitization"
    SKIN_IRRITATION = "skin_irritation"
    PHOTOTOXICITY = "phototoxicity"
    ACUTE_TOXICITY = "acute_toxicity"
    REPEATED_DOSE_TOXICITY = "repeated_dose_toxicity"
    REPRODUCTIVE_TOXICITY = "reproductive_toxicity"
    GENOTOXICITY = "genotoxicity"
    CARCINOGENICITY = "carcinogenicity"


class RiskLevel(Enum):
    """Risk assessment level."""
    SAFE = "safe"
    ACCEPTABLE = "acceptable"
    CAUTION = "caution"
    UNACCEPTABLE = "unacceptable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class EndpointAssessment:
    """Assessment of a single toxicological endpoint."""
    endpoint: FSEEndpoint
    risk_level: RiskLevel
    exposure_level: Optional[float] = None  # mg/kg/day or %
    threshold: Optional[float] = None  # NOAEL, NESIL, etc.
    margin_of_safety: Optional[float] = None
    data_source: Optional[str] = None  # e.g., "RIFM", "Literature", "QSAR"
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "endpoint": self.endpoint.value,
            "risk_level": self.risk_level.value,
            "exposure_level": self.exposure_level,
            "threshold": self.threshold,
            "margin_of_safety": self.margin_of_safety,
            "data_source": self.data_source,
            "notes": self.notes,
        }


@dataclass
class IngredientFSE:
    """FSE data for a single ingredient."""
    cas_number: str
    name: str
    concentration_percent: float
    assessments: list[EndpointAssessment] = field(default_factory=list)
    rifm_data_available: bool = False
    qsar_data_available: bool = False

    @property
    def overall_risk(self) -> RiskLevel:
        """Determine overall risk level (worst case)."""
        risk_priority = [
            RiskLevel.UNACCEPTABLE,
            RiskLevel.INSUFFICIENT_DATA,
            RiskLevel.CAUTION,
            RiskLevel.ACCEPTABLE,
            RiskLevel.SAFE,
        ]
        for risk in risk_priority:
            if any(a.risk_level == risk for a in self.assessments):
                return risk
        return RiskLevel.INSUFFICIENT_DATA

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cas_number": self.cas_number,
            "name": self.name,
            "concentration_percent": self.concentration_percent,
            "assessments": [a.to_dict() for a in self.assessments],
            "rifm_data_available": self.rifm_data_available,
            "qsar_data_available": self.qsar_data_available,
            "overall_risk": self.overall_risk.value,
        }


@dataclass
class FSEReport:
    """Full Fragrance Safety Evaluation report."""
    formula_name: str
    product_type: str
    intended_use: str
    fragrance_concentration: float  # % in final product

    # Exposure parameters
    exposure_area_cm2: Optional[float] = None
    applications_per_day: float = 1.0
    retention_factor: float = 1.0  # 1.0 for leave-on, 0.1 for rinse-off typical

    # Ingredient assessments
    ingredients: list[IngredientFSE] = field(default_factory=list)

    # Summary assessments by endpoint
    endpoint_summaries: dict[str, RiskLevel] = field(default_factory=dict)

    # Report metadata
    assessor: Optional[str] = None
    assessment_date: datetime = field(default_factory=datetime.now)
    report_number: Optional[str] = None

    # Overall conclusion
    overall_conclusion: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "formula_name": self.formula_name,
            "product_type": self.product_type,
            "intended_use": self.intended_use,
            "fragrance_concentration": self.fragrance_concentration,
            "exposure_area_cm2": self.exposure_area_cm2,
            "applications_per_day": self.applications_per_day,
            "retention_factor": self.retention_factor,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "endpoint_summaries": {k: v.value for k, v in self.endpoint_summaries.items()},
            "assessor": self.assessor,
            "assessment_date": self.assessment_date.isoformat(),
            "report_number": self.report_number,
            "overall_conclusion": self.overall_conclusion,
        }

    @property
    def has_unacceptable_risk(self) -> bool:
        """Check if any endpoint has unacceptable risk."""
        return RiskLevel.UNACCEPTABLE in self.endpoint_summaries.values()

    @property
    def has_insufficient_data(self) -> bool:
        """Check if any endpoint has insufficient data."""
        return RiskLevel.INSUFFICIENT_DATA in self.endpoint_summaries.values()


# Standard exposure parameters by product type
EXPOSURE_PARAMETERS = {
    "fine_fragrance": {
        "exposure_area_cm2": 600,
        "applications_per_day": 1.0,
        "retention_factor": 1.0,
    },
    "body_lotion": {
        "exposure_area_cm2": 15670,
        "applications_per_day": 1.0,
        "retention_factor": 1.0,
    },
    "face_cream": {
        "exposure_area_cm2": 565,
        "applications_per_day": 2.0,
        "retention_factor": 1.0,
    },
    "deodorant": {
        "exposure_area_cm2": 200,
        "applications_per_day": 1.0,
        "retention_factor": 1.0,
    },
    "shampoo": {
        "exposure_area_cm2": 580,
        "applications_per_day": 1.0,
        "retention_factor": 0.1,
    },
    "body_wash": {
        "exposure_area_cm2": 17500,
        "applications_per_day": 1.0,
        "retention_factor": 0.1,
    },
    "candle": {
        "exposure_area_cm2": 0,  # Inhalation route
        "applications_per_day": 1.0,
        "retention_factor": 0.0,  # Not dermal
    },
}
