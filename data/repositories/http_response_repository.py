from models import HttpResponse
from base import BaseRepository
from sqlmodel import Session, select
from typing import List


class HttpResponseRepository(BaseRepository[HttpResponse]):
    def __init__(self, session: Session):
        super().__init__(session, HttpResponse)
    
    def get_by_asset_id(self, asset_id: str) -> List[HttpResponse]:
        statement = select(HttpResponse).where(HttpResponse.asset_id == asset_id)
        return self.session.exec(statement).all()
    
    def get_by_status_code(self, status_code: int) -> List[HttpResponse]:
        statement = select(HttpResponse).where(HttpResponse.status_code == status_code)
        return self.session.exec(statement).all()