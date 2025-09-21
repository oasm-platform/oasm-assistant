from typing import List

class BaseEmbedding:
    name: str

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def encode(self, docs: List[str]) -> List[List[float]]:
        raise NotImplementedError("The encode method must be implemented by subclasses")


class APIBaseEmbedding(BaseEmbedding):
    baseUrl: str
    apiKey: str

    def __init__(self, name: str = None, baseUrl: str = None, apiKey: str = None):
        super().__init__(name)
        self.baseUrl = baseUrl
        self.apiKey = apiKey

    def encode(self, docs: List[str]) -> List[List[float]]:
        raise NotImplementedError("API embedding must implement encode()")