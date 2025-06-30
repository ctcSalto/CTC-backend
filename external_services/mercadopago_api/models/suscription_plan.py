from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum

class FrequencyType(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"

class FreeTrial(BaseModel):
    frequency: int = Field(..., ge=1, description="Frecuencia del período de prueba")
    frequency_type: FrequencyType = Field(..., description="Tipo de frecuencia para el período de prueba")

class AutoRecurring(BaseModel):
    frequency: int = Field(..., ge=1, description="Frecuencia de cobro")
    frequency_type: FrequencyType = Field(..., description="Tipo de frecuencia")
    repetitions: Optional[int] = Field(None, ge=1, description="Número de repeticiones (None = ilimitado)")
    billing_day: Optional[int] = Field(None, ge=1, le=31, description="Día del mes para facturar")
    billing_day_proportional: Optional[bool] = Field(None, description="Si el primer cobro es proporcional")
    free_trial: Optional[FreeTrial] = Field(None, description="Configuración del período de prueba")
    transaction_amount: float = Field(..., gt=0, description="Monto de la suscripción")
    currency_id: str = Field(..., description="ID de la moneda (ej: UYU, ARS, BRL)")

class PaymentType(BaseModel):
    id: Optional[str] = Field(None, description="ID del tipo de pago")

class PaymentMethod(BaseModel):
    id: Optional[str] = Field(None, description="ID del método de pago")

class PaymentMethodsAllowed(BaseModel):
    payment_types: Optional[List[PaymentType]] = Field(None, description="Tipos de pago permitidos")
    payment_methods: Optional[List[PaymentMethod]] = Field(None, description="Métodos de pago permitidos")

class SubscriptionPlanRequest(BaseModel):
    reason: str = Field(..., max_length=255, description="Descripción del plan")
    auto_recurring: AutoRecurring = Field(..., description="Configuración de recurrencia")
    payment_methods_allowed: Optional[PaymentMethodsAllowed] = Field(None, description="Métodos de pago permitidos")
    back_url: Optional[str] = Field(None, description="URL de retorno")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }
        json_schema_extra = {
            "example": {
                "reason": "Yoga classes",
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "repetitions": 12,
                    "billing_day": 10,
                    "billing_day_proportional": True,
                    "free_trial": {
                        "frequency": 1,
                        "frequency_type": "months"
                    },
                    "transaction_amount": 100,
                    "currency_id": "UYU"
                },
                "payment_methods_allowed": {
                    "payment_types": [
                        {"id": "credit_card"},
                        {"id": "debit_card"}
                    ],
                    "payment_methods": [
                        {"id": "visa"},
                        {"id": "master"}
                    ]
                },
                "back_url": "https://www.yoursite.com"
            }
        }

# Modelo para la respuesta de creación de plan
class SubscriptionPlanResponse(BaseModel):
    id: str
    version: Optional[int] = None
    reason: str
    status: str  # "active", "paused", "cancelled"
    date_created: str
    last_modified: str
    init_point: Optional[str] = None
    auto_recurring: AutoRecurring
    payment_methods_allowed: Optional[PaymentMethodsAllowed] = None
    back_url: Optional[str] = None
    collector_id: Optional[int] = None

# Ejemplo adicional con más opciones
class AdvancedSubscriptionPlanRequest(SubscriptionPlanRequest):
    """Modelo extendido para casos más complejos"""
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Premium Membership Plan",
                "auto_recurring": {
                    "frequency": 3,
                    "frequency_type": "months",
                    "repetitions": 4,  # 1 año total
                    "billing_day": 15,
                    "billing_day_proportional": False,
                    "free_trial": {
                        "frequency": 2,
                        "frequency_type": "weeks"
                    },
                    "transaction_amount": 29.99,
                    "currency_id": "UYU"
                },
                "payment_methods_allowed": {
                    "payment_types": [
                        {"id": "credit_card"},
                        {"id": "debit_card"},
                        {"id": "account_money"}
                    ],
                    "payment_methods": [
                        {"id": "visa"},
                        {"id": "master"},
                        {"id": "amex"}
                    ]
                },
                "back_url": "https://yoursite.com/subscription/success"
            }
        }

# Ejemplo de uso en FastAPI
"""
from fastapi import FastAPI, HTTPException
import mercadopago

app = FastAPI()

@app.post("/create-subscription-plan", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(plan: SubscriptionPlanRequest):
    sdk = mercadopago.SDK("YOUR_ACCESS_TOKEN")
    
    # Convertir el modelo a dict
    plan_data = plan.dict(exclude_none=True)
    
    # Crear el plan en MercadoPago
    plan_response = sdk.plan().create(plan_data)
    
    if plan_response["status"] == 201:
        return SubscriptionPlanResponse(**plan_response["response"])
    else:
        raise HTTPException(
            status_code=plan_response["status"],
            detail=f"Error creating subscription plan: {plan_response.get('response', {}).get('message', 'Unknown error')}"
        )

@app.get("/subscription-plan/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(plan_id: str):
    sdk = mercadopago.SDK("YOUR_ACCESS_TOKEN")
    
    plan_response = sdk.plan().get(plan_id)
    
    if plan_response["status"] == 200:
        return SubscriptionPlanResponse(**plan_response["response"])
    else:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found"
        )

@app.put("/subscription-plan/{plan_id}")
async def update_subscription_plan(plan_id: str, updates: dict):
    sdk = mercadopago.SDK("YOUR_ACCESS_TOKEN")
    
    plan_response = sdk.plan().update(plan_id, updates)
    
    if plan_response["status"] == 200:
        return plan_response["response"]
    else:
        raise HTTPException(
            status_code=plan_response["status"],
            detail="Error updating subscription plan"
        )
"""