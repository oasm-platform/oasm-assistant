from pydantic import BaseModel

class KnowledgebaseInfo(BaseModel):
    PageType: str
    pHash: int