import os
from supabase import create_client, Client
from fastapi import UploadFile, HTTPException
import uuid
from typing import List, Literal
import mimetypes
import io
from PIL import Image

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️  Pillow no está instalado. La conversión a WebP no estará disponible.")

try:
    from dotenv import load_dotenv
    # Solo carga .env si existe el archivo
    if os.path.exists('.env'):
        load_dotenv(override=True)
        print("Variables de entorno cargadas desde .env")
    else:
        print("Usando variables del sistema (producción)")
except ImportError:
    # En producción donde python-dotenv no está instalado
    print("python-dotenv no disponible, usando variables del sistema")
except Exception as e:
    print(f"Error cargando .env: {e}")

# Tipos de archivo permitidos
FileType = Literal["image", "video", "any"]

class SupabaseService:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        self.bucket_name = os.getenv("SUPABASE_BUCKET_NAME", "media")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL y SUPABASE_ANON_KEY deben estar configurados")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Configuración de tipos de archivo permitidos
        self.allowed_types = {
            "image": ["image/jpeg", "image/png", "image/gif", "image/webp"],
            "video": ["video/mp4", "video/avi", "video/mov", "video/wmv", "video/webm", "video/mkv"],
        }
        
        self.webp_quality = 85  # Calidad por defecto (0-100)
        self.webp_method = 6    # Método de compresión (0-6, 6 es el mejor pero más lento)
    
    
    def _convert_to_webp(self, file_content: bytes, quality: int = None, optimize: bool = True) -> bytes:
        """
        Convierte una imagen a formato WebP
        Args:
            file_content: Contenido del archivo original
            quality: Calidad de compresión (0-100)
            optimize: Si optimizar la imagen
        Returns:
            Contenido de la imagen en formato WebP
        """
        if not PIL_AVAILABLE:
            raise HTTPException(
                status_code=500, 
                detail="Pillow no está instalado. No se puede convertir a WebP"
            )
        
        try:
            # Cargar imagen desde bytes
            image = Image.open(io.BytesIO(file_content))
            
            # Convertir a RGB si es necesario (WebP no soporta algunos modos)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Para imágenes con transparencia, mantener el canal alpha
                if image.mode == 'P':
                    image = image.convert('RGBA')
            elif image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')
            
            # Aplicar rotación automática basada en EXIF
            image = ImageOps.exif_transpose(image)
            
            # Crear buffer para la imagen WebP
            webp_buffer = io.BytesIO()
            
            # Configurar calidad
            webp_quality = quality or self.webp_quality
            
            # Guardar como WebP
            save_kwargs = {
                'format': 'WebP',
                'quality': webp_quality,
                'optimize': optimize,
                'method': self.webp_method
            }
            
            # Si la imagen tiene transparencia, mantenerla
            if image.mode == 'RGBA':
                save_kwargs['lossless'] = False  # Usar compresión lossy para mejor tamaño
            
            image.save(webp_buffer, **save_kwargs)
            
            # Obtener bytes de la imagen WebP
            webp_bytes = webp_buffer.getvalue()
            
            print(f"🔄 Conversión WebP completada:")
            print(f"   📊 Tamaño original: {len(file_content)} bytes")
            print(f"   📈 Tamaño WebP: {len(webp_bytes)} bytes")
            print(f"   💾 Reducción: {((len(file_content) - len(webp_bytes)) / len(file_content) * 100):.1f}%")
            
            return webp_bytes
            
        except Exception as e:
            print(f"❌ Error en conversión WebP: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error al convertir imagen a WebP: {str(e)}"
            )

    def _generate_webp_filename(self, original_filename: str) -> str:
        """Genera un nombre único para el archivo WebP"""
        # Mantener el nombre base pero cambiar extensión a .webp
        base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
        return f"{uuid.uuid4()}.webp"
    def _validate_file(self, file: UploadFile, file_type: FileType = "any") -> bool:
        """Valida que el archivo sea del tipo especificado"""
        if file_type == "any":
            allowed_types = []
            for types in self.allowed_types.values():
                allowed_types.extend(types)
        else:
            allowed_types = self.allowed_types.get(file_type, [])
        
        # Verificar content type
        if file.content_type not in allowed_types:
            return False
            
        # Verificar extensión
        if file.filename:
            mime_type, _ = mimetypes.guess_type(file.filename)
            if mime_type and mime_type not in allowed_types:
                return False
        
        return True
    
    def _get_file_type(self, file: UploadFile) -> str:
        """Determina el tipo de archivo basado en su content_type"""
        for file_type, mime_types in self.allowed_types.items():
            if file.content_type in mime_types:
                return file_type
        return "unknown"
    
    def _generate_filename(self, original_filename: str) -> str:
        """Genera un nombre único para el archivo"""
        file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'bin'
        return f"{uuid.uuid4()}.{file_extension}"
    
    def _get_default_folder(self, file_type: str) -> str:
        """Obtiene la carpeta por defecto según el tipo de archivo"""
        folder_mapping = {
            "image": "images",
            "video": "videos",
        }
        return folder_mapping.get(file_type, "uploads")

    def _clean_url(self, url: str) -> str:
        """Limpia parámetros de consulta de una URL"""
        if url.endswith('?'):
            return url[:-1]  # Quita el último caracter si es ?
        elif '?' in url:
            return url.split('?')[0]  # Quita todo después del ?
        return url

    async def upload_file(self, file: UploadFile, folder: str = None, file_type: FileType = "any") -> str:
        """
        Sube un archivo a Supabase Storage
        Args:
            file: Archivo a subir
            folder: Carpeta destino (opcional, se determina automáticamente si no se especifica)
            file_type: Tipo de archivo permitido ("image", "video", "any")
        Returns: 
            URL pública del archivo
        """
        if not self._validate_file(file, file_type):
            allowed = self.allowed_types.get(file_type, list(self.allowed_types.values())[0]) if file_type != "any" else "archivos válidos"
            raise HTTPException(
                status_code=400, 
                detail=f"Archivo no válido. Solo se permiten: {allowed}"
            )
        
        try:
            # Leer el contenido del archivo
            file_content = await file.read()
            print(f"📁 Subiendo archivo: {file.filename}")
            
            # Determinar carpeta si no se especifica
            if folder is None:
                detected_type = self._get_file_type(file)
                folder = self._get_default_folder(detected_type)
            
            print(f"📂 Carpeta destino: {folder}")
            print(f"📊 Tamaño archivo original: {len(file_content)} bytes")
            
            # 🔄 CONVERSIÓN AUTOMÁTICA A WEBP PARA IMÁGENES
            content_type = file.content_type
            is_image = self._get_file_type(file) == "image"
            
            if is_image and file.content_type != "image/webp":
                print("🔄 Convirtiendo imagen a WebP...")
                try:
                    file_content = self._convert_to_webp(file_content)
                    content_type = "image/webp"
                    # Generar nombre con extensión .webp
                    filename = self._generate_webp_filename(file.filename or "image")
                    print(f"✅ Conversión a WebP completada - nuevo tamaño: {len(file_content)} bytes")
                except Exception as webp_error:
                    print(f"⚠️  Error en conversión WebP: {webp_error}")
                    print("📁 Subiendo archivo original sin conversión")
                    filename = self._generate_filename(file.filename or "file")
            else:
                filename = self._generate_filename(file.filename or "file")
                if is_image and file.content_type == "image/webp":
                    print("ℹ️  Imagen ya está en formato WebP")
            
            file_path = f"{folder}/{filename}"
            print(f"🎯 Ruta completa: {file_path}")
            
            # Subir archivo
            print("🚀 Iniciando upload...")
            response = self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
            
            print(f"📤 Respuesta upload: {response}")
            
            # Verificar si la respuesta indica éxito
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
            public_url = self._clean_url(public_url)
            print(f"🌐 URL pública: {public_url}")
            
            return public_url
            
        except Exception as e:
            print(f"💥 Error en upload_file: {str(e)}")
            print(f"💥 Tipo de error: {type(e)}")
            import traceback
            print(f"💥 Stack trace: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
    
    # Métodos específicos para facilitar el uso
    async def upload_image(self, file: UploadFile, folder: str = "images") -> str:
        """Sube una imagen a Supabase Storage"""
        return await self.upload_file(file, folder, "image")
    
    async def upload_video(self, file: UploadFile, folder: str = "videos") -> str:
        """Sube un video a Supabase Storage"""
        return await self.upload_file(file, folder, "video")
    
    async def upload_multiple_files(self, files: List[UploadFile], folder: str = None, file_type: FileType = "any") -> List[str]:
        """
        Sube múltiples archivos a Supabase Storage
        Returns: Lista de URLs públicas
        """
        urls = []
        
        for file in files:
            try:
                print(f"📁 Subiendo archivo: {file.filename}")
                url = await self.upload_file(file, folder, file_type)
                urls.append(url)
            except HTTPException as e:
                # Log del error pero continuar con los demás archivos
                print(f"Error subiendo {file.filename}: {e.detail}")
                continue
        
        if not urls:
            raise HTTPException(status_code=400, detail="No se pudo subir ningún archivo")
        
        return urls
    
    # Métodos específicos para múltiples archivos
    async def upload_multiple_images(self, files: List[UploadFile], folder: str = "images") -> List[str]:
        """Sube múltiples imágenes"""
        return await self.upload_multiple_files(files, folder, "image")
    
    async def upload_multiple_videos(self, files: List[UploadFile], folder: str = "videos") -> List[str]:
        """Sube múltiples videos"""
        return await self.upload_multiple_files(files, folder, "video")
    
    def delete_file(self, file_url: str) -> bool:
        """
        Elimina un archivo de Supabase Storage basada en su URL
        """
        try:
            # Extraer el path del archivo de la URL
            path_parts = file_url.split(f"{self.bucket_name}/")
            if len(path_parts) < 2:
                return False
            
            file_path = path_parts[1]
            
            response = self.client.storage.from_(self.bucket_name).remove([file_path])
            return response
            
        except Exception as e:
            print(f"Error eliminando archivo: {str(e)}")
            return False
    
    # Alias para mantener compatibilidad
    def delete_image(self, image_url: str) -> bool:
        """Alias para delete_file (mantiene compatibilidad)"""
        return self.delete_file(image_url)
    
    def delete_video(self, video_url: str) -> bool:
        """Elimina un video"""
        return self.delete_file(video_url)
    
    def rollback(
        self, 
        image_url: str = None, 
        image_urls: List[str] = None,
        video_url: str = None,
        video_urls: List[str] = None
    ) -> bool:
        """
        Elimina todos los archivos subidos
        """
        try:
            if image_url:
                self.delete_image(image_url)
            if image_urls:
                for url in image_urls:
                    self.delete_image(url)
            if video_url:
                self.delete_video(video_url)
            if video_urls:
                for url in video_urls:
                    self.delete_video(url)
        except Exception as e:
            print(f"Error eliminando archivos: {str(e)}")
            return False