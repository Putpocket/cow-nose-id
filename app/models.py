from pydantic import BaseModel


class Owner(BaseModel):
    id: int
    name: str
    phone: str | None = None
    farm_name: str | None = None
    farm_address: str | None = None


class Cow(BaseModel):
    id: int
    ear_tag: str
    name: str | None = None
    breed: str | None = None
    sex: str | None = None
    birth_date: str | None = None
    notes: str | None = None
    owner: Owner


class SearchMatch(BaseModel):
    rank: int
    cow_id: int
    similarity: float


class IdentifyResponse(BaseModel):
    matched: bool
    best_similarity: float
    threshold: float
    cow: Cow | None
    matches: list[SearchMatch]
    crop_box: list[int]
