import mercadopago
from external_services.mercadopago_api.models.preference import MercadoPagoPreferenceRequest
from external_services.mercadopago_api.models.suscription_plan import SubscriptionPlanRequest

import hmac
import hashlib

from utils.logger import show


class MercadoPagoController:    
    def __init__(self, access_token: str):
        self.client = mercadopago.SDK(access_token)
        
    def create_preference(self, preference: dict):
        """
        Crea una preferencia de pago en MercadoPago.
        :param preference: Datos de la preferencia.
        :return: URL de inicio de pago.
        """
        payment = self.client.preference().create(preference)
        
        # Debuggear la respuesta completa
        print("Respuesta completa:", payment)
        print("Tipo de respuesta:", type(payment))
        
        # Verificar si hay errores
        if "error" in payment:
            print("Error en la respuesta:", payment["error"])
            raise Exception(f"Error de MercadoPago: {payment['error']}")
        
        # Verificar la estructura de la respuesta
        if "response" in payment:
            print("Response keys:", payment["response"].keys())
            if "init_point" in payment["response"]:
                init_point = payment["response"]["init_point"]
                return init_point
            else:
                print("Contenido de response:", payment["response"])
                raise Exception("No se encontró 'init_point' en la respuesta")
        else:
            print("No hay 'response' en la respuesta. Keys disponibles:", payment.keys())
            # Intentar acceso directo
            if "init_point" in payment:
                return payment["init_point"]
            else:
                raise Exception("Estructura de respuesta inesperada")

    def get_preference(self, preference_id: str):
        preference = self.client.preference().get(preference_id)
        return preference["response"]
    
    def update_preference(self, preference_id: str, preference: MercadoPagoPreferenceRequest):
        updated_preference = self.client.preference().update(preference_id, preference)
        return updated_preference["response"]
    
    def cancel_preference(self, payment_id: str):
        cancellation = self.client.preference().delete(payment_id)
        return cancellation["response"]
    
    
# Subscription methods
#--------------------------------------------------------------------------
    
    def create_suscriptio_plan(self, suscription_data: dict):
        """
        Crea una suscripción en MercadoPago.
        :param subscription_data: Datos de la suscripción.
        :return: URL de inicio de pago para la suscripción.
        """
        try:
            suscription = self.client.plan().create(suscription_data)
            show(suscription)
            # Debug de la respuesta
            # Verificar la estructura de la respuesta
            if "response" in suscription:
                print("Response keys:", suscription["response"].keys())
                if "init_point" in suscription["response"]:
                    init_point = suscription["response"]["init_point"]
                    return init_point
                else:
                    print("Contenido de response:", suscription["response"])
                    raise Exception("No se encontró 'init_point' en la respuesta")
            else:
                print("No hay 'response' en la respuesta. Keys disponibles:", suscription.keys())
                # Intentar acceso directo
                if "init_point" in suscription:
                    return suscription["init_point"]
                else:
                    raise Exception("Estructura de respuesta inesperada")
        except Exception as e:
            print("Error al crear la suscripción:", e)
            raise e
    
    def get_subscription(self, subscription_id: str):
        """
        Obtiene los detalles de una suscripción.
        :param subscription_id: ID de la suscripción.
        :return: Detalles de la suscripción.
        """
        subscription = self.client.preapproval().get(subscription_id)
        return subscription["response"]
    
    def update_subscription(self, subscription_id: str, updates: dict):
        """
        Actualiza una suscripción existente.
        :param subscription_id: ID de la suscripción a actualizar.
        :param updates: Diccionario con los campos a actualizar.
        :return: Detalles de la suscripción actualizada.
        """
        updated_subscription = self.client.preapproval().update(subscription_id, updates)
        return updated_subscription["response"]
    
    def cancel_subscription(self, subscription_id: str):
        """
        Cancela una suscripción existente.
        :param subscription_id: ID de la suscripción a cancelar.
        :return: Detalles de la cancelación.
        """
        cancellation = self.client.preapproval().cancel(subscription_id)
        return cancellation["response"]
        
    