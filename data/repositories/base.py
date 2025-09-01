from sqlmodel import Session, select
from typing import Optional, List, Type, TypeVar, Generic
from models import BaseEntity

T = TypeVar('T', bound=BaseEntity)

class BaseRepository(Generic[T]):
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, id: str) -> Optional[T]:
        return self.session.get(self.model_class, id)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        statement = select(self.model_class).offset(skip).limit(limit)
        return self.session.exec(statement).all()
    
    def create(self, obj_in: T) -> T:
        self.session.add(obj_in)
        self.session.commit()
        self.session.refresh(obj_in)
        return obj_in
    
    def update(self, obj: T) -> T:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def delete(self, id: str) -> bool:
        obj = self.get_by_id(id)
        if obj:
            self.session.delete(obj)
            self.session.commit()
            return True
        return False