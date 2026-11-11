from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from mesa_platform.http import ApiError, Input, database_session
from mesa_platform.service_access import require_service_key
from services.configuration.models import Admission, EstablishmentConfiguration

def require_orders_service(request: Request):
    require_service_key(request, "MESA_ORDERS_ACCESS_KEY")


router = APIRouter(prefix="/internal/v1", dependencies=[Depends(require_orders_service)])


class AdmissionInput(Input):
    principal: str = Field(min_length=1, max_length=200)
    revision: int = Field(strict=True, gt=0, le=2147483647)
    origin: Literal["client", "counter", "tablet"]
    fulfillment: Literal["pickup", "delivery", "table"]

    @model_validator(mode="after")
    def tablet_orders_at_tables(self):
        if self.origin == "tablet" and self.fulfillment != "table":
            raise ValueError("A Comanda digital só cria pedidos para mesa.")

        return self


# Each new order needs its fulfillment feature; tablet orders also need the tablet feature.
REQUIRED_FEATURES = {
    "pickup": ("pickup", "A retirada está desabilitada para novos pedidos."),
    "delivery": ("delivery", "A entrega está desabilitada para novos pedidos."),
    "table": ("tables", "O atendimento em mesa está desabilitado para novos pedidos."),
    "tablet": ("tablet", "A Comanda digital está desabilitada para novos pedidos."),
}


def required_features(payload):
    keys = [payload.fulfillment] + (["tablet"] if payload.origin == "tablet" else [])
    return [REQUIRED_FEATURES[key] for key in keys]


class AdmissionReceipt(BaseModel):
    configuration_revision: int


@router.post("/admissions/{operation_id}", status_code=201, response_model=AdmissionReceipt)
def admit(operation_id: UUID, payload: AdmissionInput, response: Response, db=Depends(database_session)):
    configuration = db.scalar(
        select(EstablishmentConfiguration)
        .where(EstablishmentConfiguration.id == 1)
        .with_for_update()
    )
    if configuration is None:
        raise ApiError(503, "configuration_unavailable", "Configuração ainda não provisionada.")

    request_payload = payload.model_dump(mode="json")
    existing = db.get(Admission, operation_id)
    if existing is not None:
        if existing.request_payload != request_payload:
            raise ApiError(409, "idempotency_conflict", "A operação já foi utilizada com outros dados.")

        response.status_code = 200
        return AdmissionReceipt(configuration_revision=existing.configuration_revision)

    if configuration.revision != payload.revision:
        raise ApiError(409, "configuration_changed", "A configuração foi alterada.", {
            "revision": configuration.revision,
        })

    for feature, message in required_features(payload):
        if not getattr(configuration, feature):
            raise ApiError(403, "feature_disabled", message)

    receipt = AdmissionReceipt(configuration_revision=configuration.revision)
    db.add(Admission(
        operation_id=operation_id,
        request_payload=request_payload,
        configuration_revision=configuration.revision,
    ))
    db.commit()
    return receipt
