from models import Asset
from base import BaseRepository
from sqlmodel import Session, select
from typing import Optional, List


class AssetRepository(BaseRepository[Asset]):
    def __init__(self, session: Session):
        super().__init__(session, Asset)
    
    def get_by_value(self, value: str) -> Optional[Asset]:
        statement = select(Asset).where(Asset.value == value)
        return self.session.exec(statement).first()
    
    def get_primary_assets(self) -> List[Asset]:
        statement = select(Asset).where(Asset.is_primary == True)
        return self.session.exec(statement).all()
