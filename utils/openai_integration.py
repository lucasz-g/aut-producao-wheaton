import json
import os

from openai import AsyncOpenAI
from dotenv import load_dotenv


load_dotenv()

DEFAULT_BASE_URL = "https://wheaton-openai.services.ai.azure.com/openai/v1"
DEFAULT_DEPLOYMENT_NAME = "gpt-4.1-mini"

ESQUEMA_ANOTACOES_INTERPRETADAS = {
    "type": "object",
    "properties": {
        "maquinas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "maquina": {
                        "type": "string",
                        "description": "Identificador da máquina, igual à chave do JSON de entrada.",
                    },
                    "prefixo": {
                        "type": "string",
                        "description": (
                            "Prefixo ao qual a anotação pertence. Use string vazia "
                            "quando as anotações não estiverem agrupadas por prefixo."
                        ),
                    },
                    "anotacoes": {
                        "type": "string",
                        "description": (
                            "Anotações padronizadas e resumidas em texto corrido."
                        ),
                    },
                },
                "required": ["maquina", "prefixo", "anotacoes"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["maquinas"],
    "additionalProperties": False,
}

INSTRUCOES_ANOTACOES = (
    "Você analisa as anotações dos operadores de uma fábrica de vidros. "
    "O JSON de entrada traz as anotações brutas do dia agrupadas por máquina e, "
    "quando disponível, por prefixo.\n"
    "Para cada máquina e prefixo, padronize e resuma as anotações em texto corrido, "
    "descrevendo o que aconteceu na produção, sem repetir os campos linha a linha.\n"
    "Use somente as informações presentes no JSON, sem inventar dados. "
    "Devolva uma entrada por máquina e prefixo presentes na entrada; quando as "
    "anotações não estiverem agrupadas por prefixo, devolva o prefixo como string vazia."
)


def _criar_cliente() -> AsyncOpenAI:
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Configure a variável de ambiente AZURE_OPENAI_API_KEY antes de gerar o resumo."
        )

    base_url = os.getenv("AZURE_OPENAI_BASE_URL", DEFAULT_BASE_URL)

    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def _deployment_name() -> str:
    return os.getenv("AZURE_OPENAI_DEPLOYMENT", DEFAULT_DEPLOYMENT_NAME)


async def get_anotacoes_interpretadas(anotacoes_json: str) -> list[dict]:
    """Resume as anotações com a IA, devolvendo uma entrada por máquina e prefixo."""
    async with _criar_cliente() as client:
        response = await client.responses.create(
            model=_deployment_name(),
            input=f"{INSTRUCOES_ANOTACOES}\n\n{anotacoes_json}",
            text={
                "format": {
                    "type": "json_schema",
                    "name": "anotacoes_interpretadas",
                    "strict": True,
                    "schema": ESQUEMA_ANOTACOES_INTERPRETADAS,
                }
            },
        )

    try:
        return json.loads(response.output_text).get("maquinas", [])
    except json.JSONDecodeError as erro:
        raise RuntimeError(
            "A IA não retornou um JSON válido com as anotações resumidas."
        ) from erro
