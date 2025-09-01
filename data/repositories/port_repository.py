from models import Port
from base import BaseRepository
from sqlmodel import Session, select
from typing import List


class PortRepository(BaseRepository[Port]):
    def __init__(self, session: Session):
        super().__init__(session, Port)
    
    def get_by_asset_id(self, asset_id: str) -> List[Port]:
        statement = select(Port).where(Port.asset_id == asset_id)
        return self.session.exec(statement).all()