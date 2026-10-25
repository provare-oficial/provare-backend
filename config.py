"""
Configurações do Provare — carregadas do arquivo .env
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017/provare"

    # JWT
    secret_key: str = "chave-secreta-troque-em-producao"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 dias

    # Cloudinary (fotos e vídeos)
    cloudinary_cloud_name: str = "wvlxwmvv"
    cloudinary_api_key: str = "538811565722977"
    cloudinary_api_secret: str = ""
    cloudinary_upload_preset: str = "provare-media"

    # Claude API
    anthropic_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""
    stripe_price_pro: str = ""
    stripe_price_studio: str = ""

    # Email (Resend)
    resend_api_key: str = ""
    from_email: str = "onboarding@resend.dev"

    # App
    app_url: str = "https://provare.com.br"
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Instância global das configurações
settings = Settings()
