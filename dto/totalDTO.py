from pydantic import BaseModel
from typing import List

class totalDTO(BaseModel):
    symbol: str
    value_usd: float
    percentage: float

class totalDTOList(BaseModel):
    items: List[totalDTO] = []

    def append(self, item: totalDTO):
        self.items.append(item)