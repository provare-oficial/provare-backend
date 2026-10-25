"""
Serviço de IA para geração de mensagens WhatsApp elegantes via Claude Haiku
"""
import logging
from typing import Optional
import anthropic
from config import settings

logger = logging.getLogger(__name__)

# Mensagem de fallback caso a API falhe
FALLBACK_MESSAGES = [
    "{client_name} ✦\n\nO trabalho avança.\n\nSeu Provare Book foi atualizado com os registros mais recentes.\n📲 {book_url}",
    "{client_name} ✦\n\nNova etapa documentada.\n\nCada detalhe registrado, como sempre.\n📲 {book_url}",
    "{client_name} ✦\n\nO processo continua.\n\nAs últimas atualizações estão no seu Provare Book.\n📲 {book_url}",
]


async def generate_whatsapp_message(
    company_name: str,
    company_industry: str,
    client_name: str,
    project_title: str,
    current_phase_title: Optional[str],
    is_first_send: bool,
    previous_messages: list[str],
    book_url: str,
    current_time_brasilia: str,
) -> str:
    """
    Gera mensagem WhatsApp única, elegante e personalizada via Claude Haiku.
    Cada mensagem é diferente das anteriores.
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY não configurada, usando fallback")
        return _fallback_message(client_name, book_url, is_first_send)

    # Contexto das mensagens anteriores para garantir variação
    historico = ""
    if previous_messages:
        historico = "\n\nMensagens anteriores enviadas (NÃO repita o estilo nem as frases):\n"
        historico += "\n---\n".join(previous_messages[-3:])  # últimas 3

    envio_info = "PRIMEIRO ENVIO" if is_first_send else f"REENVIO (já enviado {len(previous_messages)} vezes)"

    prompt = f"""Você é um redator de comunicação premium para a empresa "{company_name}" ({company_industry}).

Escreva UMA mensagem WhatsApp para o cliente **{client_name}** sobre o projeto "{project_title}".

Contexto:
- Fase atual: {current_phase_title or "em andamento"}
- Tipo de envio: {envio_info}
- Horário: {current_time_brasilia}
- Link do documento: {book_url}
{historico}

REGRAS DE ESTILO (obrigatórias):
1. Comece com o primeiro nome do cliente + um símbolo elegante (✦ ✧ · ∘)
2. Segunda linha: VAZIA (linha em branco)
3. Terceira linha: frase visual, poética e impactante sobre o que está acontecendo na obra. Máximo 15 palavras. Sem clichês.
4. Quarta linha: VAZIA
5. Quinta linha: frase de contexto sobre a fase atual, elegante e específica. Máximo 15 palavras.
6. Sexta linha: VAZIA
7. Sétima linha: o link com emoji 📲
8. Oitava linha: VAZIA
9. Nona linha: horário · nome da empresa (ex: "14:32 · Pietra Milano")

PROIBIDO:
- Exclamação (!!)
- "Incrível", "Fantástico", "Maravilhoso"
- Tom corporativo ou de marketing
- Repetir frases de mensagens anteriores
- Mais de 9 linhas no total

Escreva APENAS a mensagem, sem explicações."""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        message = response.content[0].text.strip()
        logger.info(f"Mensagem WhatsApp gerada para {client_name}")
        return message
    except Exception as e:
        logger.error(f"Erro ao gerar mensagem via Claude: {e}")
        return _fallback_message(client_name, book_url, is_first_send)


def _fallback_message(client_name: str, book_url: str, is_first_send: bool) -> str:
    """Mensagem de fallback elegante quando a API falha."""
    import random
    from datetime import datetime

    first_name = client_name.split()[0] if client_name else client_name
    template = random.choice(FALLBACK_MESSAGES)
    return template.format(client_name=first_name, book_url=book_url)
