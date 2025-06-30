from fastapi import APIRouter, HTTPException, Request, status, Query, Depends
from fastapi.responses import JSONResponse

from database.database import Services, get_services, get_session
from sqlmodel import Session

from external_services.mercadopago_api.models.preference import MercadoPagoPreferenceRequest
from external_services.mercadopago_api.models.suscription_plan import SubscriptionPlanRequest

import os
import hmac
import hashlib
import json

from dotenv import load_dotenv

# Cargar .env en desarrollo, usar variables del sistema en producción
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass  # En producción no existe .env, usa variables del sistema

from utils.logger import show

router = APIRouter(prefix="/mercadopago", tags=["Mercadopago"])

# Endpoints de Pago
@router.post("/payment", response_model=str, status_code=200)
async def create_payment(
    preference: MercadoPagoPreferenceRequest,
    services: Services = Depends(get_services),
    #current_user: UserRead = Depends(get_current_active_user),
    #session: Session = Depends(get_session)
    ) -> str:
    try:
        show(preference)
        preference_dict = preference.model_dump(mode="json", exclude_none=True)
        init_point: str =services.mercadoPagoController.create_preference(preference_dict)
        return init_point
    except Exception as e:
        show(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payment", response_model=dict, status_code=200)
async def get_payment(
    services: Services = Depends(get_services),
    preference_id: str = Query(..., description="ID de la preferencia"),
    #current_user: UserRead = Depends(get_current_active_user),
    #session: Session = Depends(get_session)
    ) -> str:
    try:
        show(preference_id)
        preference =services.mercadoPagoController.get_preference(preference_id)
        show(preference)
        return preference
    except Exception as e:
        show(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/payment", response_model=dict, status_code=200)
async def delete_payment(
    services: Services = Depends(get_services),
    preference_id: str = Query(..., description="ID de la preferencia"),
    #current_user: UserRead = Depends(get_current_active_user),
    #session: Session = Depends(get_session)
    ) -> str:
    try:
        show(preference_id)
        preference =services.mercadoPagoController.cancel_payment(preference_id)
        show(preference)
        return preference
    except Exception as e:
        show(e)
        raise HTTPException(status_code=500, detail=str(e))
    
# ---------------------------------------------------------------------------
# Endpoints de Suscripción
    
@router.post("/suscription-plan", response_model=str, status_code=200)
async def get_payment(
    subscription: SubscriptionPlanRequest,
    services: Services = Depends(get_services),
    #current_user: UserRead = Depends(get_current_active_user),
    #session: Session = Depends(get_session)
) -> str:
    try:
        show(subscription)
        subscription_dict = subscription.model_dump(mode="json", exclude_none=True)
        show(subscription_dict)
        init_point: str = services.mercadoPagoController.create_suscriptio_plan(subscription_dict)
        return init_point
    except Exception as e:
        show(e)
        raise HTTPException(status_code=500, detail=str(e))
    
    
# ---------------------------------------------------------------------------
# Webhooks de MercadoPago
    
@router.post("/payment-webhook", status_code=200)
async def mercadopago_webhook(
    request: Request, 
    services: Services = Depends(get_services), 
    session: Session = Depends(get_session)
    ):
    try:
        print("Llego al webhook")
        
        headers = request.headers
        x_signature = headers.get('x-signature')
        x_request_id = headers.get('x-request-id')
        
        if not x_signature or not x_request_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Headers requeridos faltantes"
            )
        
        body = await request.json()
        data_id = body.get('data', {}).get('id')
        
        if not data_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="ID de datos faltante"
            )
        
        # Verificación de signature (mismo código que arriba)
        signature_parts = x_signature.split(',')
        if len(signature_parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Formato de signature inválido"
            )
        
        ts, signature = signature_parts
        ts_key, ts_value = ts.split('=', 1)
        signature_key, signature_value = signature.split('=', 1)
        
        signature_template = f"id:{data_id};request-id:{x_request_id};ts:{ts_value};"
        
        webhook_secret = os.getenv('MERCADOPAGO_WEBHOOK_SECRET_KEY')
        cyphed_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signature_template.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if cyphed_signature != signature_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Solicitud no autorizada"
            )
        
        # Usar el SDK más nuevo (si tienes mercadopago >= 2.0.0)
        import mercadopago as mp
        
        access_token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
        client = mp.SDK(access_token=access_token)
        payment_client = client.payment()
        payment_data = payment_client.get(data_id)
        
        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pago no encontrado"
            )
        
        show(f"payment: {json.dumps(payment_data, indent=2, default=str)}")
        
        """
        Colocar Logica de verificaciones y guardado de datos en la base de datos
        # Ejemplo de cómo podrías guardar el pago en la base de datos
        from database.models import Payment, User
        
        user_id = payment_data.metadata.get('user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de usuario no encontrado en metadata"
            )
        
        user_found = db.query(User).filter(User.id == user_id).first()
        if not user_found:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        new_payment_record = Payment(
            total=payment_data.transaction_amount,
            user_id=user_found.id,
            payment_id=payment_data.id,
            provider="mercadopago"
        )
        
        db.add(new_payment_record)
        db.commit()
        db.refresh(new_payment_record)
        
        print(f"newPaymentRecord: {json.dumps(new_payment_record.__dict__, indent=2, default=str)}")
        """
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok"}
        )
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error en webhook: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en el webhook de Mercado Pago"
        )
        
        
@router.post("/suscription-webhook", status_code=200)
async def mercadopago_webhook(
    request: Request, 
    services: Services = Depends(get_services), 
    session: Session = Depends(get_session)
    ):
    try:
        print("Llego al webhook")
        
        headers = request.headers
        x_signature = headers.get('x-signature')
        x_request_id = headers.get('x-request-id')
        
        if not x_signature or not x_request_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Headers requeridos faltantes"
            )
        
        body = await request.json()
        data_id = body.get('data', {}).get('id')
        
        if not data_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="ID de datos faltante"
            )
        
        # Verificación de signature (mismo código que arriba)
        signature_parts = x_signature.split(',')
        if len(signature_parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Formato de signature inválido"
            )
        
        ts, signature = signature_parts
        ts_key, ts_value = ts.split('=', 1)
        signature_key, signature_value = signature.split('=', 1)
        
        signature_template = f"id:{data_id};request-id:{x_request_id};ts:{ts_value};"
        
        webhook_secret = os.getenv('MERCADOPAGO_WEBHOOK_SECRET_KEY')
        cyphed_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signature_template.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if cyphed_signature != signature_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Solicitud no autorizada"
            )
        
        # Usar el SDK más nuevo (si tienes mercadopago >= 2.0.0)
        import mercadopago as mp
        
        access_token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
        client = mp.SDK(access_token=access_token)
        payment_client = client.preapproval()
        payment_data = payment_client.get(data_id)
        
        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pago no encontrado"
            )
        
        show(f"payment: {json.dumps(payment_data, indent=2, default=str)}")
        
        """
        Colocar Logica de verificaciones y guardado de datos en la base de datos
        # Ejemplo de cómo podrías guardar el pago en la base de datos
        from database.models import Payment, User
        
        user_id = payment_data.metadata.get('user_id')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de usuario no encontrado en metadata"
            )
        
        user_found = db.query(User).filter(User.id == user_id).first()
        if not user_found:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado"
            )
        
        new_payment_record = Payment(
            total=payment_data.transaction_amount,
            user_id=user_found.id,
            payment_id=payment_data.id,
            provider="mercadopago"
        )
        
        db.add(new_payment_record)
        db.commit()
        db.refresh(new_payment_record)
        
        print(f"newPaymentRecord: {json.dumps(new_payment_record.__dict__, indent=2, default=str)}")
        """
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok"}
        )
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error en webhook: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en el webhook de Mercado Pago"
        )