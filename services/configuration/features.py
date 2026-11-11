"""Pure feature rules owned by the configuration service."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog: Literal[True] = True
    orders: Literal[True] = True
    pickup: StrictBool
    delivery: StrictBool
    tables: StrictBool
    tablet: StrictBool
    tv: StrictBool

    @field_validator("catalog", "orders", mode="before")
    @classmethod
    def require_boolean_true(cls, value):
        if value is not True:
            raise ValueError("Funcionalidades obrigatórias devem ser true.")

        return value

    @model_validator(mode="after")
    def validate_dependencies(self) -> Self:
        if not (self.pickup or self.delivery or self.tables):
            raise ValueError("Selecione pelo menos uma modalidade de atendimento.")

        if self.tablet and not self.tables:
            raise ValueError("Comanda digital exige atendimento em mesa.")

        return self

    def required_services(self) -> list[str]:
        services = ["configuration", "catalog", "orders"]

        if self.delivery:
            services.append("deliveries")

        if self.tables:
            services.append("tables")

        return services


class Product(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    name: str = Field(min_length=1, max_length=80)
    features: Features
    services: list[str]

    @model_validator(mode="after")
    def validate_services(self) -> Self:
        if self.services != self.features.required_services():
            raise ValueError("Serviços devem corresponder às funcionalidades selecionadas.")

        return self
