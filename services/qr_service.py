"""
Serviço de geração de QR Codes para autenticidade do Provare Book
"""
import io
import base64
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from config import settings


def generate_qr_code_base64(book_slug: str) -> str:
    """
    Gera um QR code para o link de verificação do Provare Book.
    Retorna a imagem em base64 para embutir diretamente no HTML.
    """
    verify_url = f"{settings.app_url}/verificar/{book_slug}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    # Gera imagem com cantos arredondados
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        back_color=(10, 10, 10),
        fill_color=(201, 168, 76),  # Dourado Provare
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def get_verify_url(book_slug: str) -> str:
    """Retorna a URL de verificação do Provare Book."""
    return f"{settings.app_url}/verificar/{book_slug}"
