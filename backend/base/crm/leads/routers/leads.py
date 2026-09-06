# Copyright 2025 FARA CRM
# Leads module — leads router

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from backend.base.crm.auth_token.app import AuthTokenApp

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment

router_private = APIRouter(
    tags=["Leads"],
    dependencies=[Depends(AuthTokenApp.verify_access)],
)


@router_private.post("/leads/{lead_id}/create_sale")
async def create_sale_from_lead(req: Request, lead_id: int):
    """Ручное создание продажи из лида (кнопка на форме лида).

    Вся механика — в Lead.create_sale. Нужна и для повторных заказов: у одного
    лида много продаж. Доступ к лиду проверяют штатные правила leads (ORM get,
    чужой/несуществующий → RecordNotFound → 404); саму продажу создаёт система.
    """
    env: "Environment" = req.app.state.env
    lead = await env.models.lead.get(lead_id)
    sale_id = await lead.create_sale()
    return {"sale_id": sale_id}
