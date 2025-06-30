import os
from supabase import create_client, Client
from fastapi import UploadFile, HTTPException
import uuid
from typing import List
import mimetypes

from utils.logger import show

from dotenv import load_dotenv
# Cargar .env en desarrollo, usar variables del sistema en producción
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass  # En producción no existe .env, usa variables del sistema

class SupabaseService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.bucket_name = os.getenv("SUPABASE_BUCKET_NAME", "images")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL y SUPABASE_ANON_KEY deben estar configurados")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
    
    def _validate_image(self, file: UploadFile) -> bool:
        """Valida que el archivo sea una imagen"""
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        
        # Verificar content type
        if file.content_type not in allowed_types:
            return False
            
        # Verificar extensión
        if file.filename:
            mime_type, _ = mimetypes.guess_type(file.filename)
            if mime_type not in allowed_types:
                return False
        
        return True
    
    def _generate_filename(self, original_filename: str) -> str:
        """Genera un nombre único para el archivo"""
        file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'jpg'
        return f"{uuid.uuid4()}.{file_extension}"
    

    async def upload_image(self, file: UploadFile, folder: str = "uploads") -> str:
        """
        Sube una imagen a Supabase Storage
        Returns: URL pública de la imagen
        """
        if not self._validate_image(file):
            raise HTTPException(status_code=400, detail="Archivo no válido. Solo se permiten imágenes.")
        
        try:
            # Leer el contenido del archivo
            file_content = await file.read()
            print(f"📁 Subiendo archivo: {file.filename}")
            print(f"📂 Carpeta destino: {folder}")
            print(f"📊 Tamaño archivo: {len(file_content)} bytes")
            
            # Generar nombre único
            filename = self._generate_filename(file.filename or "image.jpg")
            file_path = f"{folder}/{filename}"
            print(f"🎯 Ruta completa: {file_path}")
            
            # Subir archivo - La respuesta de Supabase Storage es diferente
            print("🚀 Iniciando upload...")
            response = self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            print(f"📤 Respuesta upload: {response}")
            print(f"📤 Tipo de respuesta: {type(response)}")
            
            # Verificar si la respuesta indica éxito
            # Supabase devuelve un dict con 'data' si es exitoso, o un error
            if hasattr(response, 'data') and response.data:
                print("✅ Upload exitoso")
            elif isinstance(response, dict) and 'error' in response:
                print(f"❌ Error en upload: {response['error']}")
                raise HTTPException(status_code=500, detail=f"Error al subir: {response['error']}")
            else:
                print("✅ Upload completado")
            
            # Obtener URL pública
            print("🔗 Obteniendo URL pública...")
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            print(f"🌐 URL pública: {public_url}")
            
            return public_url
            
        except Exception as e:
            print(f"💥 Error en upload_image: {str(e)}")
            print(f"💥 Tipo de error: {type(e)}")
            import traceback
            print(f"💥 Stack trace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error al procesar la imagen: {str(e)}")
    
    async def upload_multiple_images(self, files: List[UploadFile], folder: str = "uploads") -> List[str]:
        """
        Sube múltiples imágenes a Supabase Storage
        Returns: Lista de URLs públicas
        """
        urls = []
        
        for file in files:
            try:
                url = await self.upload_image(file, folder)
                urls.append(url)
            except HTTPException as e:
                # Log del error pero continuar con las demás imágenes
                print(f"Error subiendo {file.filename}: {e.detail}")
                continue
        
        if not urls:
            raise HTTPException(status_code=400, detail="No se pudo subir ninguna imagen")
        
        return urls
    
    def delete_image(self, image_url: str) -> bool:
        """
        Elimina una imagen de Supabase Storage basada en su URL
        """
        try:
            # Extraer el path del archivo de la URL
            path_parts = image_url.split(f"{self.bucket_name}/")
            if len(path_parts) < 2:
                return False
            
            file_path = path_parts[1]
            
            response = self.client.storage.from_(self.bucket_name).remove([file_path])
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error eliminando imagen: {str(e)}")
            return False