"""
Context factors repository
Risk score multipliers based on environmental context
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from data.database.models.context_factor import ContextFactor


class ContextFactorsRepository:
    """Repository for context factor operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_factor(self, factor_type: str, factor_value: str) -> Optional[ContextFactor]:
        """Get a specific context factor"""
        return self.session.query(ContextFactor)\
            .filter(and_(
                ContextFactor.factor_type == factor_type,
                ContextFactor.factor_value == factor_value
            ))\
            .first()

    def get_by_type(self, factor_type: str) -> List[ContextFactor]:
        """Get all factors of a specific type"""
        return self.session.query(ContextFactor)\
            .filter(ContextFactor.factor_type == factor_type)\
            .all()

    def calculate_context_multiplier(self, context: Dict) -> float:
        """
        Calculate combined risk multiplier from context

        Args:
            context: Dictionary with context information
                {
                    "environment": "production",
                    "data_sensitivity": "payment",
                    "exposure": "public_internet",
                    "asset_criticality": "critical"
                }

        Returns:
            Combined multiplier value
        """
        multiplier = 1.0

        for factor_type, factor_value in context.items():
            factor = self.get_factor(factor_type, factor_value)
            if factor:
                multiplier *= factor.multiplier

        return multiplier

    def get_environment_multiplier(self, environment: str) -> float:
        """Get multiplier for environment type"""
        factor = self.get_factor("environment", environment)
        return factor.multiplier if factor else 1.0

    def get_data_sensitivity_multiplier(self, data_type: str) -> float:
        """Get multiplier for data sensitivity"""
        factor = self.get_factor("data_sensitivity", data_type)
        return factor.multiplier if factor else 1.0

    def get_exposure_multiplier(self, exposure: str) -> float:
        """Get multiplier for exposure level"""
        factor = self.get_factor("exposure", exposure)
        return factor.multiplier if factor else 1.0

    def get_asset_criticality_multiplier(self, criticality: str) -> float:
        """Get multiplier for asset criticality"""
        factor = self.get_factor("asset_criticality", criticality)
        return factor.multiplier if factor else 1.0

    def get_all_multipliers(self) -> Dict:
        """Get all available multipliers grouped by type"""
        factors = self.session.query(ContextFactor).all()

        result = {}
        for factor in factors:
            if factor.factor_type not in result:
                result[factor.factor_type] = {}

            result[factor.factor_type][factor.factor_value] = {
                "multiplier": factor.multiplier,
                "description": factor.description,
                "guidance": factor.guidance
            }

        return result

    def create_factor(
        self,
        factor_type: str,
        factor_name: str,
        factor_value: str,
        multiplier: float,
        description: Optional[str] = None,
        guidance: Optional[str] = None,
        examples: Optional[str] = None
    ) -> ContextFactor:
        """Create a new context factor"""
        factor = ContextFactor(
            factor_type=factor_type,
            factor_name=factor_name,
            factor_value=factor_value,
            multiplier=multiplier,
            description=description,
            guidance=guidance,
            examples=examples
        )
        self.session.add(factor)
        self.session.commit()
        return factor
