import json
import re
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TITULO_RELATORIO = "Relatório Diário de Produção"

COR_PRINCIPAL = colors.HexColor("#1f3864")
COR_SECUNDARIA = colors.HexColor("#4472c4")
COR_CABECALHO_TABELA = colors.HexColor("#e7eaf3")
COR_HORA_TABELA = colors.HexColor("#f4f6fb")
COR_BORDA_TABELA = colors.HexColor("#b7c0d6")

METRICAS = [
    ("Objetivo %", "Objetivo"),
    ("Empacotado %", "Empacotado"),
    ("Rejeição %", "Rejeição"),
    ("Emp - Rejeitado %", "Emp - Rejeitado"),
]


def _remover_formatacao_markdown(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    return texto


def _texto_seguro(texto) -> str:
    return escape(_remover_formatacao_markdown(str(texto)))


def _formatar_percentual(valor) -> str:
    if valor is None or valor == "":
        return "—"
    try:
        return f"{float(valor):.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return str(valor)


def _construir_estilos() -> dict[str, ParagraphStyle]:
    estilos = getSampleStyleSheet()

    return {
        "titulo": ParagraphStyle(
            "TituloRelatorio",
            parent=estilos["Title"],
            alignment=TA_CENTER,
            textColor=COR_PRINCIPAL,
            spaceAfter=0.2 * cm,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloRelatorio",
            parent=estilos["Normal"],
            alignment=TA_CENTER,
            fontSize=9,
            textColor=colors.HexColor("#666666"),
            spaceAfter=0.6 * cm,
        ),
        "maquina": ParagraphStyle(
            "TituloMaquina",
            parent=estilos["Heading1"],
            fontSize=15,
            leading=19,
            textColor=COR_PRINCIPAL,
            spaceBefore=0.2 * cm,
            spaceAfter=0.1 * cm,
        ),
        "prefixo": ParagraphStyle(
            "TituloPrefixo",
            parent=estilos["Heading2"],
            fontSize=12,
            leading=15,
            textColor=COR_SECUNDARIA,
            spaceBefore=0.35 * cm,
            spaceAfter=0.15 * cm,
        ),
        "rotulo": ParagraphStyle(
            "RotuloSecao",
            parent=estilos["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=colors.HexColor("#444444"),
            spaceBefore=0.2 * cm,
            spaceAfter=0.1 * cm,
        ),
        "texto": ParagraphStyle(
            "TextoRelatorio",
            parent=estilos["BodyText"],
            fontSize=10.5,
            leading=15,
            alignment=TA_JUSTIFY,
            spaceAfter=0.2 * cm,
        ),
        "item": ParagraphStyle(
            "ItemRelatorio",
            parent=estilos["BodyText"],
            fontSize=10.5,
            leading=15,
            leftIndent=0.5 * cm,
            firstLineIndent=-0.35 * cm,
            spaceAfter=0.1 * cm,
        ),
        "vazio": ParagraphStyle(
            "TextoVazio",
            parent=estilos["BodyText"],
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#888888"),
            spaceAfter=0.2 * cm,
        ),
        "celula": ParagraphStyle(
            "CelulaTabela",
            parent=estilos["Normal"],
            fontSize=9.5,
            leading=12,
            alignment=TA_CENTER,
        ),
        "celula_cabecalho": ParagraphStyle(
            "CelulaCabecalho",
            parent=estilos["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=TA_CENTER,
            textColor=COR_PRINCIPAL,
        ),
        "celula_cabecalho_esq": ParagraphStyle(
            "CelulaCabecalhoEsquerda",
            parent=estilos["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=COR_PRINCIPAL,
        ),
        "celula_hora": ParagraphStyle(
            "CelulaHora",
            parent=estilos["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=COR_PRINCIPAL,
        ),
        "celula_descricao": ParagraphStyle(
            "CelulaDescricao",
            parent=estilos["Normal"],
            fontSize=10,
            leading=13.5,
        ),
        "heading_texto": estilos["Heading2"],
    }


def _tabela_desempenho(campos: dict, estilos: dict, largura: float) -> Table:
    cabecalhos = ["OP"] + [rotulo for _, rotulo in METRICAS]
    valores = [str(campos.get("OP") or "—")] + [
        _formatar_percentual(campos.get(chave)) for chave, _ in METRICAS
    ]

    dados = [
        [
            Paragraph(_texto_seguro(texto), estilos["celula_cabecalho"])
            for texto in cabecalhos
        ],
        [Paragraph(_texto_seguro(texto), estilos["celula"]) for texto in valores],
    ]

    tabela = Table(dados, colWidths=[largura / len(cabecalhos)] * len(cabecalhos))
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COR_CABECALHO_TABELA),
                ("GRID", (0, 0), (-1, -1), 0.5, COR_BORDA_TABELA),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    return tabela


def _hora_exibicao(hora) -> str:
    """Formata 'HH:MM' como '04h45'."""
    texto = str(hora or "").strip()
    correspondencia = re.fullmatch(r"(\d{1,2}):(\d{2})", texto)

    if not correspondencia:
        return texto

    return f"{int(correspondencia.group(1)):02d}h{correspondencia.group(2)}"


def _eventos_linha_do_tempo(anotacao) -> list[tuple[str, str]]:
    """Extrai os pares (hora, descrição) da linha do tempo."""
    if isinstance(anotacao, dict):
        anotacao = [anotacao]

    if not isinstance(anotacao, list):
        return []

    eventos = []

    for registro in anotacao:
        if isinstance(registro, dict) and "descricao" in registro:
            hora = _hora_exibicao(registro.get("hora"))
            descricao = str(registro.get("descricao") or "").strip()
        elif isinstance(registro, dict):
            hora = ""
            descricao = " | ".join(
                f"{chave}: {valor}"
                for chave, valor in registro.items()
                if valor not in (None, "")
            )
        else:
            hora = ""
            descricao = str(registro).strip()

        if descricao:
            eventos.append((hora, descricao))

    return eventos


def _tabela_linha_do_tempo(
    eventos: list[tuple[str, str]],
    estilos: dict,
    largura: float,
) -> Table:
    largura_hora = 2.2 * cm

    dados = [
        [
            Paragraph("Hora", estilos["celula_cabecalho"]),
            Paragraph("Ocorrência", estilos["celula_cabecalho_esq"]),
        ]
    ]

    for hora, descricao in eventos:
        dados.append(
            [
                Paragraph(_texto_seguro(hora or "—"), estilos["celula_hora"]),
                Paragraph(_texto_seguro(descricao), estilos["celula_descricao"]),
            ]
        )

    tabela = Table(
        dados,
        colWidths=[largura_hora, largura - largura_hora],
        repeatRows=1,
    )

    estilo_tabela = [
        ("BACKGROUND", (0, 0), (-1, 0), COR_CABECALHO_TABELA),
        ("BACKGROUND", (0, 1), (0, -1), COR_HORA_TABELA),
        ("GRID", (0, 0), (-1, -1), 0.5, COR_BORDA_TABELA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]

    tabela.setStyle(TableStyle(estilo_tabela))

    return tabela


def _blocos_anotacao(
    anotacao,
    observacoes,
    estilos: dict,
    largura: float,
) -> list:
    blocos = []
    eventos = _eventos_linha_do_tempo(anotacao)

    if eventos:
        blocos.append(_tabela_linha_do_tempo(eventos, estilos, largura))
    elif isinstance(anotacao, str) and anotacao.strip():
        blocos.append(Paragraph(_texto_seguro(anotacao.strip()), estilos["texto"]))

    texto_observacoes = str(observacoes or "").strip()

    if texto_observacoes:
        blocos.append(
            KeepTogether(
                [
                    Paragraph("Observações do turno", estilos["rotulo"]),
                    Paragraph(_texto_seguro(texto_observacoes), estilos["texto"]),
                ]
            )
        )

    if not blocos:
        blocos.append(Paragraph("Sem anotações registradas.", estilos["vazio"]))

    return blocos


def _blocos_prefixo(
    prefixo: str,
    campos,
    anotacao_maquina,
    observacoes_maquina,
    estilos: dict,
    largura: float,
) -> list:
    campos = campos if isinstance(campos, dict) else {}
    anotacao = campos.get("anotacoes", anotacao_maquina)
    observacoes = campos.get("observacoes", observacoes_maquina)

    cabecalho = [
        Paragraph(f"Prefixo {_texto_seguro(prefixo)}", estilos["prefixo"]),
        _tabela_desempenho(campos, estilos, largura),
        Paragraph("Linha do tempo do turno", estilos["rotulo"]),
    ]

    return [
        KeepTogether(cabecalho),
        *_blocos_anotacao(anotacao, observacoes, estilos, largura),
    ]


def _blocos_maquina(maquina: str, conteudo, estilos: dict, largura: float) -> list:
    conteudo = conteudo if isinstance(conteudo, dict) else {}
    anotacao_maquina = conteudo.get("anotacoes")
    observacoes_maquina = conteudo.get("observacoes")
    prefixos = conteudo.get("prefixos") or {}

    blocos = [
        KeepTogether(
            [
                Paragraph(f"Máquina {_texto_seguro(maquina)}", estilos["maquina"]),
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=COR_SECUNDARIA,
                    spaceAfter=0.25 * cm,
                ),
            ]
        )
    ]

    if isinstance(prefixos, dict) and prefixos:
        for prefixo, campos in prefixos.items():
            blocos.extend(
                _blocos_prefixo(
                    prefixo,
                    campos,
                    anotacao_maquina,
                    observacoes_maquina,
                    estilos,
                    largura,
                )
            )
    else:
        blocos.append(Paragraph("Linha do tempo do turno", estilos["rotulo"]))
        blocos.extend(
            _blocos_anotacao(
                anotacao_maquina, observacoes_maquina, estilos, largura
            )
        )

    return blocos


def _conteudo_estruturado(dados: dict, estilos: dict, largura: float) -> list:
    conteudo = []

    for indice, (maquina, dados_maquina) in enumerate(dados.items()):
        if indice:
            conteudo.append(PageBreak())

        conteudo.extend(_blocos_maquina(maquina, dados_maquina, estilos, largura))

    return conteudo


def _conteudo_texto(texto: str, estilos: dict) -> list:
    """Renderização de reserva, para quando o resumo não é um JSON estruturado."""
    conteudo = []

    for linha_original in texto.strip().splitlines():
        linha = linha_original.strip()

        if not linha:
            conteudo.append(Spacer(1, 0.15 * cm))
            continue

        if linha.startswith("#"):
            linha = linha.lstrip("#").strip()
            estilo = estilos["heading_texto"]
        elif linha.startswith(("- ", "* ")):
            linha = f"• {linha[2:].strip()}"
            estilo = estilos["item"]
        else:
            estilo = estilos["texto"]

        conteudo.append(Paragraph(_texto_seguro(linha), estilo))

    return conteudo


def _desenhar_rodape(canvas, documento) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(2 * cm, 1.2 * cm, TITULO_RELATORIO)
    canvas.drawRightString(
        documento.pagesize[0] - 2 * cm,
        1.2 * cm,
        f"Página {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def gerar_pdf_resumo_anotacoes(resumo_anotacoes: str | dict) -> bytes:
    """
    Gera o PDF do relatório diário a partir do JSON com as anotações
    interpretadas pela IA (string JSON ou dict já desserializado).

    Estrutura esperada:
        {"14": {"prefixos": {"LB -0478-N1": {
            "OP": "198176", "Objetivo %": 60.0, ...,
            "anotacoes": [{"hora": "04:45", "descricao": "..."}],
            "observacoes": "..."}}}}

    Cada máquina começa em uma nova página, com o título "Máquina {número}" e,
    por prefixo, uma tabela de desempenho, a linha do tempo do turno (hora x
    ocorrência) e as observações sem hora identificada. Se o conteúdo recebido
    não for um JSON, ele é renderizado como texto/markdown simples.
    """
    if isinstance(resumo_anotacoes, dict):
        dados = resumo_anotacoes
    elif isinstance(resumo_anotacoes, str) and resumo_anotacoes.strip():
        try:
            dados = json.loads(resumo_anotacoes)
        except json.JSONDecodeError:
            dados = None
    else:
        raise ValueError("O resumo das anotações não pode estar vazio.")

    if isinstance(dados, dict) and not dados:
        raise ValueError("O resumo das anotações não pode estar vazio.")

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=TITULO_RELATORIO,
    )

    estilos = _construir_estilos()

    conteudo = [
        Paragraph(TITULO_RELATORIO, estilos["titulo"]),
        Paragraph(
            f"Gerado em {datetime.now():%d/%m/%Y às %H:%M}",
            estilos["subtitulo"],
        ),
    ]

    if isinstance(dados, dict):
        conteudo.extend(_conteudo_estruturado(dados, estilos, documento.width))
    else:
        conteudo.extend(_conteudo_texto(str(resumo_anotacoes), estilos))

    documento.build(
        conteudo,
        onFirstPage=_desenhar_rodape,
        onLaterPages=_desenhar_rodape,
    )

    return buffer.getvalue()
