from sqlmodel import SQLModel, Field

class IpAssetsView(SQLModel, table=True):   
    __tablename__ = "ip_assets_view"
    
    asset_id: str = Field(primary_key=True)
    ip_address: str = Field(alias="ip")

class StatusCodeAssetsView(SQLModel, table=True):
    __tablename__ = "status_code_assets_view"
    
    status_code: int = Field(primary_key=True)
    asset_id: str = Field(primary_key=True)