from models import IpAssetsView, StatusCodeAssetsView
from sqlmodel import Session, select
from typing import List


class ViewRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def get_ip_assets(self) -> List[IpAssetsView]:
        statement = select(IpAssetsView)
        return self.session.exec(statement).all()
    
    def get_status_code_assets(self) -> List[StatusCodeAssetsView]:
        statement = select(StatusCodeAssetsView)
        return self.session.exec(statement).all()