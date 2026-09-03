from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator


T = TypeVar("T", int, float)


class DomainModel(BaseModel):
    """Immutable base model for seeded marketplace data."""

    model_config = ConfigDict(frozen=True)


class ValueRange(DomainModel, Generic[T]):
    minimum: T
    maximum: T

    @model_validator(mode="after")
    def validate_order(self) -> "ValueRange[T]":
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self
