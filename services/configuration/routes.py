from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, update

from mesa_platform.http import ApiError, Input, database_session
from services.configuration.access import admin_mutation, admin_session
from services.configuration.features import Features, Product
from services.configuration.models import EstablishmentConfiguration

router = APIRouter(prefix="/v1")
PRESET_PATH = Path(__file__).resolve().parents[2] / "products"
PRESETS = tuple(
    Product.model_validate_json((PRESET_PATH / f"{name}.json").read_text(encoding="utf-8"))
    for name in ("lanchonete", "delivery", "restaurante")
)


class Configuration(BaseModel):
    revision: int
    features: Features
    updated_at: datetime


class ConfigurationUpdate(Input):
    expected_revision: int = Field(strict=True, gt=0, le=2147483647)
    features: Features


def read_configuration(db):
    row = db.get(EstablishmentConfiguration, 1)
    if row is None:
        raise ApiError(503, "configuration_unavailable", "Configuração ainda não provisionada.")

    features = Features.model_validate(row, from_attributes=True)
    return Configuration(revision=row.revision, features=features, updated_at=row.updated_at)


@router.get("/configuration", response_model=Configuration)
def get_configuration(db=Depends(database_session)):
    return read_configuration(db)


@router.put("/configuration", response_model=Configuration, dependencies=[Depends(admin_mutation)])
def save_configuration(payload: ConfigurationUpdate, db=Depends(database_session)):
    model = EstablishmentConfiguration
    row = db.execute(
        update(model)
        .where(model.id == 1, model.revision == payload.expected_revision)
        .values(
            **payload.features.model_dump(exclude={"catalog", "orders"}),
            revision=model.revision + 1,
            updated_at=func.now(),
        )
        .returning(model.revision, model.updated_at)
    ).one_or_none()

    if row is None:
        current = read_configuration(db)
        raise ApiError(409, "configuration_changed", "A configuração foi alterada.", {
            "revision": current.revision,
        })

    db.commit()
    return Configuration(revision=row.revision, features=payload.features, updated_at=row.updated_at)


@router.get("/configuration/presets", response_model=list[Product], dependencies=[Depends(admin_session)])
def list_presets():
    return PRESETS


@router.get("/configuration/export", response_model=Product, dependencies=[Depends(admin_session)])
def export_configuration(db=Depends(database_session)):
    features = read_configuration(db).features
    name = next((preset.name for preset in PRESETS if preset.features == features), "personalizado")
    return Product(version=1, name=name, features=features, services=features.required_services())
