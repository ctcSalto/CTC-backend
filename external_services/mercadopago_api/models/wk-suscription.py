from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class WebhookData(BaseModel):
    id: str = Field(..., description="ID del recurso que cambió")

class MercadoPagoWebhookPayload(BaseModel):
    """Modelo actualizado para el formato real de webhooks de MercadoPago"""
    action: str = Field(..., description="Acción que disparó el webhook")
    application_id: int = Field(..., description="ID de la aplicación")
    data: WebhookData = Field(..., description="Datos del recurso")
    date: datetime = Field(..., description="Fecha del evento")
    entity: str = Field(..., description="Entidad del webhook (preapproval, payment, etc.)")
    id: int = Field(..., description="ID único del evento")
    type: str = Field(..., description="Tipo de notificación")
    version: int = Field(..., description="Versión del webhook")

class PaymentWebhookData(BaseModel):
    """Datos específicos para webhooks de pagos"""
    id: str
    status: Optional[str] = None
    external_reference: Optional[str] = None
    preference_id: Optional[str] = None
    payment_method_id: Optional[str] = None
    payment_type_id: Optional[str] = None
    transaction_amount: Optional[float] = None
    currency_id: Optional[str] = None
    date_created: Optional[datetime] = None
    date_approved: Optional[datetime] = None

class SubscriptionWebhookData(BaseModel):
    """Datos específicos para webhooks de suscripciones"""
    id: str
    status: Optional[str] = None
    external_reference: Optional[str] = None
    reason: Optional[str] = None