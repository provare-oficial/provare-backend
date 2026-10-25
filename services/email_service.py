"""
Serviço de envio de emails via Resend (magic links)
"""
import logging
import resend
from config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


async def send_magic_link(email: str, name: str, token: str) -> bool:
    """
    Envia magic link de acesso por email.
    O usuário clica no link e é autenticado automaticamente, sem senha.
    """
    magic_url = f"{settings.app_url}/auth/verify/{token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #0A0A0A; margin: 0; padding: 40px 20px; }}
        .container {{ max-width: 480px; margin: 0 auto; }}
        .logo {{ color: #C9A84C; font-size: 24px; font-weight: 300; letter-spacing: 4px; margin-bottom: 40px; }}
        .card {{ background: #111111; border: 1px solid #2A2A2A; border-radius: 12px; padding: 40px; }}
        h1 {{ color: #F5F0E8; font-size: 22px; font-weight: 400; margin: 0 0 12px; }}
        p {{ color: #888888; font-size: 15px; line-height: 1.6; margin: 0 0 32px; }}
        .btn {{ display: inline-block; background: #C9A84C; color: #0A0A0A; text-decoration: none;
                padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 15px; }}
        .footer {{ color: #444444; font-size: 12px; margin-top: 32px; text-align: center; }}
        .url {{ color: #555555; font-size: 12px; word-break: break-all; margin-top: 24px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="logo">PROVARE</div>
        <div class="card">
          <h1>Olá, {name.split()[0]}</h1>
          <p>Clique no botão abaixo para acessar sua conta Provare. O link é válido por 30 minutos.</p>
          <a href="{magic_url}" class="btn">Acessar minha conta</a>
          <div class="url">Ou copie: {magic_url}</div>
        </div>
        <div class="footer">
          Se você não solicitou este acesso, ignore este email.<br>
          © {__import__('datetime').datetime.now().year} Provare — provare.com.br
        </div>
      </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": f"Provare <{settings.from_email}>",
            "to": [email],
            "subject": "Seu link de acesso ao Provare",
            "html": html,
        }
        resend.Emails.send(params)
        logger.info(f"Magic link enviado para {email}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar magic link para {email}: {e}")
        return False


async def send_notification(email: str, subject: str, html: str) -> bool:
    """Envia email de notificação genérico."""
    try:
        resend.Emails.send({
            "from": f"Provare <{settings.from_email}>",
            "to": [email],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")
        return False
