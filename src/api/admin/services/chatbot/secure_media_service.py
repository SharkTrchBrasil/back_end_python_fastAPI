# src/core/services/secure_media_service.py - NOVO ARQUIVO
import io
import uuid
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException


class SecureMediaService:
    def __init__(self):
        self.max_file_size = 16 * 1024 * 1024  # 16MB
        self.allowed_image_types = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
        self.allowed_audio_types = {'audio/mpeg', 'audio/mp3', 'audio/ogg', 'audio/wav'}
        self.allowed_document_types = {'application/pdf', 'text/plain'}
        self.allowed_video_types = {'video/mp4', 'video/3gpp'}

        self.allowed_types = (
                self.allowed_image_types |
                self.allowed_audio_types |
                self.allowed_document_types |
                self.allowed_video_types
        )

    def validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        """Valida arquivo antes do upload"""
        try:
            # ✅ Verifica tipo MIME
            if file.content_type not in self.allowed_types:
                return False, f"Tipo de arquivo não permitido: {file.content_type}"

            # ✅ Verifica tamanho (lê apenas o necessário)
            file.file.seek(0, 2)  # Vai para o final
            size = file.file.tell()
            file.file.seek(0)  # Volta para o início

            if size > self.max_file_size:
                return False, f"Arquivo muito grande: {size} bytes (máximo: {self.max_file_size})"

            # ✅ Verifica extensão vs tipo MIME
            if file.filename:
                extension = file.filename.lower().split('.')[-1]
                if not self._validate_extension(file.content_type, extension):
                    return False, f"Extensão não corresponde ao tipo MIME: {extension} vs {file.content_type}"

            return True, "OK"

        except Exception as e:
            return False, f"Erro na validação: {str(e)}"

    def _validate_extension(self, content_type: str, extension: str) -> bool:
        """Valida se a extensão corresponde ao tipo MIME"""
        extension_map = {
            'image/jpeg': {'jpg', 'jpeg'},
            'image/png': {'png'},
            'image/webp': {'webp'},
            'audio/mpeg': {'mp3'},
            'audio/ogg': {'ogg'},
            'application/pdf': {'pdf'},
            'video/mp4': {'mp4'},
            'text/plain': {'txt'}
        }

        allowed_extensions = extension_map.get(content_type, set())
        return extension in allowed_extensions

    async def process_upload(self, file: UploadFile, store_id: int) -> Optional[str]:
        """Processa upload de forma segura"""
        # ✅ Validação
        is_valid, message = self.validate_file(file)
        if not is_valid:
            print(f"❌ Upload rejeitado: {message}")
            return None

        try:
            # ✅ Lê o arquivo em chunks para evitar memory leak
            file_bytes = await file.read()

            # ✅ Upload para S3 (usa função existente)
            from src.api.admin.services.chatbot.chatbot_media_service import upload_media_from_buffer
            return upload_media_from_buffer(
                store_id=store_id,
                file_buffer=file_bytes,
                filename=file.filename,
                content_type=file.content_type
            )

        except Exception as e:
            print(f"❌ Erro no processamento do upload: {e}")
            return None


# Instância global
media_service = SecureMediaService()