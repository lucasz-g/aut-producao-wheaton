import re
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _remover_formatacao_markdown(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    return texto


def gerar_pdf_resumo_anotacoes(resumo_anotacoes: str) -> bytes:
    if not isinstance(resumo_anotacoes, str) or not resumo_anotacoes.strip():
        raise ValueError("O resumo das anotações não pode estar vazio.")

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Resumo das anotações",
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloResumo",
        parent=estilos["Title"],
        alignment=TA_CENTER,
        spaceAfter=0.8 * cm,
    )
    estilo_texto = ParagraphStyle(
        "TextoResumo",
        parent=estilos["BodyText"],
        fontSize=11,
        leading=16,
        spaceAfter=0.25 * cm,
    )
    estilo_item = ParagraphStyle(
        "ItemResumo",
        parent=estilo_texto,
        leftIndent=0.5 * cm,
        firstLineIndent=-0.35 * cm,
    )

    conteudo = [
        Paragraph("Resumo das anotações", estilo_titulo),
    ]

    for linha_original in resumo_anotacoes.strip().splitlines():
        linha = linha_original.strip()

        if not linha:
            conteudo.append(Spacer(1, 0.15 * cm))
            continue

        if linha.startswith("#"):
            linha = linha.lstrip("#").strip()
            estilo = estilos["Heading2"]
        elif linha.startswith(("- ", "* ")):
            linha = f"• {linha[2:].strip()}"
            estilo = estilo_item
        else:
            estilo = estilo_texto

        linha = escape(_remover_formatacao_markdown(linha))
        conteudo.append(Paragraph(linha, estilo))

    documento.build(conteudo)
    return buffer.getvalue()
