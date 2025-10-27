"""
CWE (Common Weakness Enumeration) repository
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_
from data.database.models.cwe import CWE


class CWERepository:
    """Repository for CWE operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, cwe_id: str) -> Optional[CWE]:
        """Get CWE by ID"""
        return self.session.query(CWE)\
            .filter(CWE.cwe_id == cwe_id)\
            .first()

    def search_by_name(self, keyword: str) -> List[CWE]:
        """Search CWE by name or description"""
        search = f"%{keyword}%"
        return self.session.query(CWE)\
            .filter(or_(
                CWE.name.ilike(search),
                CWE.description.ilike(search)
            ))\
            .all()

    def get_by_capec(self, capec_id: str) -> List[CWE]:
        """Get CWEs related to a CAPEC attack pattern"""
        return self.session.query(CWE)\
            .filter(CWE.capec_ids.contains([capec_id]))\
            .all()

    def get_children(self, cwe_id: str) -> List[CWE]:
        """Get child CWEs"""
        cwe = self.get_by_id(cwe_id)
        if not cwe or not cwe.child_cwe_ids:
            return []

        return self.session.query(CWE)\
            .filter(CWE.cwe_id.in_(cwe.child_cwe_ids))\
            .all()

    def get_parent(self, cwe_id: str) -> Optional[CWE]:
        """Get parent CWE"""
        cwe = self.get_by_id(cwe_id)
        if not cwe or not cwe.parent_cwe_id:
            return None

        return self.get_by_id(cwe.parent_cwe_id)

    def get_weakness_chain(self, cwe_id: str) -> List[CWE]:
        """Get the full weakness chain (from root to current CWE)"""
        chain = []
        current = self.get_by_id(cwe_id)

        while current:
            chain.insert(0, current)
            if not current.parent_cwe_id:
                break
            current = self.get_by_id(current.parent_cwe_id)

        return chain

    def get_mitigation_strategies(self, cwe_id: str) -> Optional[str]:
        """Get mitigation strategies for a CWE"""
        cwe = self.get_by_id(cwe_id)
        return cwe.potential_mitigations if cwe else None

    def create_cwe(
        self,
        cwe_id: str,
        name: str,
        description: str,
        abstraction: Optional[str] = None,
        parent_cwe_id: Optional[str] = None,
        likelihood: Optional[str] = None,
        potential_mitigations: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> CWE:
        """Create a new CWE entry"""
        cwe = CWE(
            cwe_id=cwe_id,
            name=name,
            description=description,
            abstraction=abstraction,
            parent_cwe_id=parent_cwe_id,
            likelihood=likelihood,
            potential_mitigations=potential_mitigations,
            embedding=embedding
        )
        self.session.add(cwe)
        self.session.commit()
        return cwe

    def get_high_risk_cwes(self) -> List[CWE]:
        """Get CWEs with high exploitation likelihood"""
        return self.session.query(CWE)\
            .filter(CWE.likelihood == 'High')\
            .all()
