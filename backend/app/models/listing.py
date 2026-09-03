from enum import StrEnum

from pydantic import Field

from app.models.common import DomainModel


class Market(StrEnum):
    BROOKLYN = "Brooklyn"
    MANHATTAN = "Manhattan"
    QUEENS = "Queens"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    UNCONFIRMED = "unconfirmed"


class Listing(DomainModel):
    id: str
    lister_id: str
    name: str
    market: Market
    monthly_price: int = Field(gt=0)
    availability_status: AvailabilityStatus = AvailabilityStatus.UNCONFIRMED
