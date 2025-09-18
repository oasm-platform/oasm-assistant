from pydantic.v1 import BaseModel, Field, validator
from typing import Optional, Literal


class EmbeddingConfig(BaseModel):
    name: str = Field(..., description="The name of the SentenceTransformer model")
    device: Optional[str] = Field(None, description="Device: cpu, cuda, cuda:0, mps")
    dim: Optional[int] = Field(None, description="Expected embedding dimension")

    @validator('name')
    def check_model_name(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Model name must be a non-empty string")
        return value
    
    @validator("device")
    def check_device(cls, value):
        if value is None:
            return value
        v = value.lower().strip()
        if v not in ("cpu", "mps") and not v.startswith("cuda"):
            raise ValueError("Device must be one of {'cpu','mps','cuda','cuda:<index>'}")
        return v

    @validator("dim")
    def check_dim(cls, value):
        if value is not None and value <= 0:
            raise ValueError("Dimension must be a positive integer")
        return value

class BaseEmbedding():
    name: str

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def encode(self, text: str):
        raise NotImplementedError("The encode method must be implemented by subclasses")


class APIBaseEmbedding(BaseEmbedding):
    baseUrl: str
    apiKey: str

    def __init__(self, name: str = None, baseUrl: str = None, apiKey: str = None):
        super().__init__(name)
        self.baseUrl = baseUrl
        self.apiKey = apiKey

    def encode(self, text: str):

        raise NotImplementedError("API embedding must implement encode()")