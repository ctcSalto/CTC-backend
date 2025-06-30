from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class BackUrls(BaseModel):
    success: str
    failure: str
    pending: str

class Item(BaseModel):
    id: str
    title: str
    currency_id: str = "UYU"
    picture_url: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    unit_price: float = Field(..., gt=0, description="Precio unitario del item")

class Phone(BaseModel):
    area_code: Optional[str] = None
    number: Optional[str] = None

class Identification(BaseModel):
    type: Optional[str] = str
    number: Optional[str] = str

class Address(BaseModel):
    street_name: Optional[str] = None
    street_number:  Optional[int] = None
    zip_code: Optional[str] = None

class Payer(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    surname: Optional[str] = None
    phone: Optional[Phone] = None
    identification: Optional[Identification] = None
    address: Optional[Address] = None

class PaymentMethods(BaseModel):
    excluded_payment_types: Optional[List[str]] = Field(default_factory=list)
    excluded_payment_methods: Optional[List[str]] = Field(default_factory=list)
    installments: Optional[int] = None
    default_payment_method_id: Optional[str] = None

class MercadoPagoPreferenceRequest(BaseModel):
    auto_return: Optional[str] = "approved"  # Puede ser "approved", "all", "none"
    back_urls: Optional[BackUrls] = None
    statement_descriptor: Optional[str] = None
    binary_mode: Optional[bool] = False
    external_reference: Optional[str] = None
    items: List[Item]
    payer: Optional[Payer] = None
    payment_methods: Optional[PaymentMethods] = None
    expires: Optional[bool] = None
    expiration_date_from: Optional[datetime] = None
    expiration_date_to: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        # Permite que los campos con datetime sean serializados como ISO strings
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        # Ejemplo de uso
        json_schema_extra = {
            "example": {
                "auto_return": "approved",
                "back_urls": {
                    "success": "https://httpbin.org/get?back_url=success",
                    "failure": "https://httpbin.org/get?back_url=failure",
                    "pending": "https://httpbin.org/get?back_url=pending"
                },
                "statement_descriptor": "TestStore",
                "binary_mode": False,
                "external_reference": "IWD1238971",
                "items": [
                    {
                        "id": "item-ID-1234",
                        "title": "Mi producto",
                        "currency_id": "UYU",
                        "picture_url": "https://www.mercadopago.com/org-img/MP3/home/logomp3.gif",
                        "description": "Descripción del Item",
                        "quantity": 1,
                        "unit_price": 75.76
                    }
                ],
                "payer": {
                    "email": "test_user_12398378192@testuser.com",
                    "name": "Juan",
                    "surname": "Lopez",
                    "phone": {
                        "area_code": "11",
                        "number": "1523164589"
                    },
                    "identification": {
                        "type": "DNI",
                        "number": "12345678"
                    },
                    "address": {
                        "street_name": "Street",
                        "street_number": 123,
                        "zip_code": "1406"
                    }
                },
                "payment_methods": {
                    "excluded_payment_types": [],
                    "excluded_payment_methods": [],
                    "installments": 12,
                    "default_payment_method_id": "account_money"
                },
                "expires": True,
                "expiration_date_from": "2025-01-01T12:00:00.000-04:00",
                "expiration_date_to": "2026-12-31T12:00:00.000-04:00",
                "metadata": {
                    "user_id": 1
                }
            }
        }

# Ejemplo de uso en FastAPI
"""
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()

@app.post("/create-preference")
async def create_preference(preference: MercadoPagoPreferenceRequest):
    # Convertir el modelo a dict para enviar a MercadoPago
    preference_data = preference.dict(exclude_none=True)
    
    # Aquí harías la llamada a la API de MercadoPago
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=preference_data,
            headers={
                "Authorization": f"Bearer {YOUR_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            raise HTTPException(status_code=400, detail="Error creating preference")
"""