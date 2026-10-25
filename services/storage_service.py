"""
Serviço de armazenamento de arquivos via Cloudinary
"""
import cloudinary
import cloudinary.uploader
import cloudinary.api
import logging
import os
from config import settings

logger = logging.getLogger(__name__)


def _configure_cloudinary():
    """Configura as credenciais do Cloudinary."""
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


async def upload_file(
    file_bytes: bytes,
    filename: str,
    company_id: str,
    project_id: str,
    content_type: str = None,
) -> str:
    """
    Faz upload de um arquivo para o Cloudinary.
    Retorna a URL pública do arquivo.
    """
    import asyncio

    _configure_cloudinary()

    # Define o public_id com o caminho: provare/companies/{company_id}/projects/{project_id}/{filename_sem_ext}
    name_without_ext = os.path.splitext(filename)[0]
    public_id = f"provare/companies/{company_id}/projects/{project_id}/{name_without_ext}"

    # Determina resource_type baseado no content_type
    resource_type = "auto"
    if content_type:
        if content_type.startswith("video/"):
            resource_type = "video"
        elif content_type.startswith("image/"):
            resource_type = "image"

    def _upload():
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            invalidate=True,
        )
        return result.get("secure_url", "")

    url = await asyncio.get_event_loop().run_in_executor(None, _upload)
    logger.info(f"Arquivo enviado para Cloudinary: {public_id}")
    return url


async def upload_file_unsigned(
    file_bytes: bytes,
    filename: str,
    company_id: str,
    project_id: str,
    content_type: str = None,
) -> str:
    """
    Faz upload usando preset não assinado (sem API Secret).
    Usa o preset 'provare-media' configurado no Cloudinary.
    """
    import asyncio

    _configure_cloudinary()

    name_without_ext = os.path.splitext(filename)[0]
    public_id = f"companies/{company_id}/projects/{project_id}/{name_without_ext}"

    resource_type = "auto"
    if content_type:
        if content_type.startswith("video/"):
            resource_type = "video"
        elif content_type.startswith("image/"):
            resource_type = "image"

    def _upload():
        result = cloudinary.uploader.unsigned_upload(
            file_bytes,
            upload_preset=settings.cloudinary_upload_preset,
            public_id=public_id,
            resource_type=resource_type,
        )
        return result.get("secure_url", "")

    url = await asyncio.get_event_loop().run_in_executor(None, _upload)
    logger.info(f"Arquivo enviado para Cloudinary (unsigned): {public_id}")
    return url


async def delete_file(url: str) -> bool:
    """Remove um arquivo do Cloudinary pela URL pública."""
    import asyncio

    try:
        _configure_cloudinary()

        # Extrai o public_id da URL do Cloudinary
        # URL format: https://res.cloudinary.com/{cloud_name}/image/upload/v{version}/{public_id}.{ext}
        parts = url.split("/upload/")
        if len(parts) < 2:
            logger.error(f"URL inválida para deletar: {url}")
            return False

        # Remove version prefix (v1234567890/) se existir
        path_with_ext = parts[1]
        if path_with_ext.startswith("v") and "/" in path_with_ext:
            path_with_ext = path_with_ext.split("/", 1)[1]

        # Remove extensão do arquivo
        public_id = os.path.splitext(path_with_ext)[0]

        # Determina resource_type pela URL
        resource_type = "image"
        if "/video/upload/" in url:
            resource_type = "video"
        elif "/raw/upload/" in url:
            resource_type = "raw"

        def _delete():
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type,
                invalidate=True,
            )
            return result.get("result") == "ok"

        success = await asyncio.get_event_loop().run_in_executor(None, _delete)
        if success:
            logger.info(f"Arquivo removido do Cloudinary: {public_id}")
        else:
            logger.warning(f"Arquivo não encontrado no Cloudinary: {public_id}")
        return success

    except Exception as e:
        logger.error(f"Erro ao remover arquivo do Cloudinary: {e}")
        return False


async def get_signed_url(public_id: str, expires_in: int = 3600) -> str:
    """Gera uma URL assinada para acesso temporário (para arquivos privados)."""
    import asyncio
    from cloudinary.utils import cloudinary_url

    _configure_cloudinary()

    def _sign():
        url, _ = cloudinary_url(
            public_id,
            sign_url=True,
            type="authenticated",
            expires_at=int(__import__("time").time()) + expires_in,
        )
        return url

    return await asyncio.get_event_loop().run_in_executor(None, _sign)
