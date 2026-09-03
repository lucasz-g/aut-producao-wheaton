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
                        "type": "array",
                        "description": (
                            "Linha do tempo do turno: uma entrada por ocorrência "
                            "com hora identificada, em ordem cronológica."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "hora": {
                                    "type": "string",
                                    "description": (
                                        "Hora da ocorrência no formato HH:MM "
                                        "(24 horas). Quando a anotação indicar um "
                                        "intervalo, use a hora de início."
                                    ),
                                },
                                "descricao": {
                                    "type": "string",
                                    "description": (
                                        "O que aconteceu nessa hora, em uma frase "
                                        "curta e objetiva, sem repetir a hora."
                                    ),
                                },
                            },
                            "required": ["hora", "descricao"],
                            "additionalProperties": False,
                        },
                    },
                    "observacoes": {
                        "type": "string",
                        "description": (
                            "Resumo curto das informações do turno que não têm "
                            "hora identificada. String vazia quando não houver."
                        ),
                    },
                },
                "required": ["maquina", "prefixo", "anotacoes", "observacoes"],
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
    "Para cada máquina e prefixo, organize as anotações como uma linha do tempo do "
    "turno: uma entrada em 'anotacoes' para cada ocorrência que tenha hora "
    "identificada, com a hora em 'hora' (formato HH:MM, 24 horas) e o que aconteceu "
    "em 'descricao'.\n"
    "Regras da linha do tempo:\n"
    "- Ordene as entradas cronologicamente, seguindo o turno (começa às 06:00 e "
    "termina às 06:00 do dia seguinte).\n"
    "- Uma entrada por ocorrência: não junte dois horários diferentes na mesma "
    "entrada e não crie duas entradas para a mesma ocorrência.\n"
    "- Escreva 'descricao' em uma frase curta, objetiva e no passado, sem repetir a "
    "hora e sem começar com conectivos como 'e', 'após' ou 'então'. Deve fazer "
    "sentido lida isoladamente (diga a mesa, seção ou cavidade quando a anotação "
    "informar).\n"
    "- Quando a anotação descrever um intervalo (ex.: 'parada das 08:45 até 11:35'), "
    "use a hora de início e cite o fim ou a duração na descrição.\n"
    "- Normalize horas como '4h45', '445' ou '4:45' para '04:45'.\n"
    "Em 'observacoes', resuma em texto corrido curto apenas o que não tem hora "
    "identificada (condições gerais do turno, códigos de desvio recorrentes, "
    "pendências). Use string vazia quando tudo já estiver na linha do tempo.\n"
    "Use somente as informações presentes no JSON, sem inventar dados nem horários. "
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
