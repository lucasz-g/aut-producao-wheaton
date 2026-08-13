import os

from openai import AsyncOpenAI
from dotenv import load_dotenv


load_dotenv()

DEFAULT_BASE_URL = "https://wheaton-openai.services.ai.azure.com/openai/v1"
DEFAULT_DEPLOYMENT_NAME = "gpt-4.1-mini"


async def get_openai_response(prompt: str) -> str:
    api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Configure a variável de ambiente AZURE_OPENAI_API_KEY antes de gerar o resumo."
        )

    base_url = os.getenv("AZURE_OPENAI_BASE_URL", DEFAULT_BASE_URL)
    deployment_name = os.getenv(
        "AZURE_OPENAI_DEPLOYMENT",
        DEFAULT_DEPLOYMENT_NAME,
    )

    input_ia = (
        "Padronize e resuma as anotações abaixo, separando o resultado por máquina. "
        "Use somente as informações presentes no JSON.\n\n"
        f"{prompt}"
    )

    async with AsyncOpenAI(base_url=base_url, api_key=api_key) as client:
        response = await client.responses.create(
            model=deployment_name,
            input=input_ia,
        )

    return response.output_text
