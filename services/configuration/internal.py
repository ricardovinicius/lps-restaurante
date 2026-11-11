from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
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
    origin: Literal["client", "counter"]
    fulfillment: Literal["pickup", "delivery"]


FULFILLMENT_NAMES = {"pickup": "A retirada", "delivery": "A entrega"}


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

    if not getattr(configuration, payload.fulfillment):
        name = FULFILLMENT_NAMES[payload.fulfillment]
        raise ApiError(403, "feature_disabled", f"{name} está desabilitada para novos pedidos.")

    receipt = AdmissionReceipt(configuration_revision=configuration.revision)
    db.add(Admission(
        operation_id=operation_id,
        request_payload=request_payload,
        configuration_revision=configuration.revision,
    ))
    db.commit()
    return receipt
