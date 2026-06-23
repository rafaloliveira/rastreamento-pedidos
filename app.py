# app.py
# Aplicacao Streamlit de consulta publica de entregas e notas fiscais.
#
# Fluxo geral:
#   1. Carrega (com cache) os dados do arquivo CSV hospedado no Google Drive.
#   2. Normaliza os campos usados na pesquisa (CPF/CNPJ e Numero da NF).
#   3. Exibe um formulario para o usuario informar CPF/CNPJ + Numero da NF.
#   4. Filtra os registros pela chave composta (documento + nota fiscal).
#   5. Exibe o(s) resultado(s) em cards, do mais recente para o mais antigo.

import base64
import os
import re
from datetime import datetime
from io import BytesIO
from typing import Optional

import pandas as pd
import streamlit as st
from PIL import Image, ImageChops

import config

# Caminhos das logos institucionais. A pasta assets/ e os arquivos sao
# opcionais: se nao existirem, a area correspondente e simplesmente ocultada.
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
LOGO_FUNDO_BRANCO_PATH = os.path.join(ASSETS_DIR, "logo_fundo_branco.jpg")

# Altura fixa (em pixels) aplicada a todas as logos do cabecalho. A largura
# de cada uma e calculada automaticamente para preservar a proporcao
# original, evitando o desalinhamento causado por imagens com canvas
# de tamanhos/proporcoes diferentes.
ALTURA_LOGO_PX = 80


# ---------------------------------------------------------------------------
# Funcoes utilitarias de normalizacao
# ---------------------------------------------------------------------------

def somente_numeros(valor) -> str:
    """Remove qualquer caractere que nao seja dígito de 0 a 9.

    Usada tanto para os valores digitados pelo usuario quanto para as
    colunas do CSV, garantindo que a comparacao seja feita sempre
    sobre uma representacao puramente numerica (sem pontos, barras,
    tracos, espacos ou caracteres invisiveis como 'Â').
    """
    if valor is None:
        return ""
    texto = str(valor)
    return re.sub(r"\D", "", texto)


def remover_zeros_a_esquerda(valor_numerico: str) -> str:
    """Remove zeros à esquerda para comparar números de NF de forma
    equivalente (ex.: '00012345' e '12345' devem ser considerados iguais).
    Mantém pelo menos um dígito (caso o valor seja só zeros).
    """
    valor_sem_zeros = valor_numerico.lstrip("0")
    return valor_sem_zeros if valor_sem_zeros else "0"


def formatar_chave_nf(valor) -> str:
    """Normaliza um numero de nota fiscal para fins de comparacao:
    extrai apenas digitos e remove zeros a esquerda.
    """
    return remover_zeros_a_esquerda(somente_numeros(valor))


def formatar_data(valor) -> str:
    """Formata uma data (string ou Timestamp) para exibicao em DD/MM/AAAA.
    Retorna '-' quando o valor estiver vazio/nulo ou nao puder ser convertido.
    """
    if valor is None:
        return "-"
    if isinstance(valor, pd.Timestamp):
        if pd.isna(valor):
            return "-"
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return "-"
    return texto


def formatar_valor_monetario(valor) -> str:
    """Formata um valor numerico como moeda brasileira (R$ 0.000,00)."""
    try:
        numero = float(
            str(valor)
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        return f"R$ {numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        texto = str(valor).strip()
        return texto if texto and texto.lower() != "nan" else "-"


def texto_ou_padrao(valor, padrao: str = "Não informado") -> str:
    """Retorna o texto do valor ou um texto padrao quando vazio/nulo."""
    if valor is None:
        return padrao
    texto = str(valor).strip()
    if texto == "" or texto.lower() == "nan":
        return padrao
    return texto


# ---------------------------------------------------------------------------
# Carregamento e preparacao dos dados
# ---------------------------------------------------------------------------

@st.cache_data(ttl=config.CACHE_TTL_SECONDS)
def load_data():
    """Carrega o arquivo CSV do Google Drive, limpa e normaliza os dados.

    O resultado fica em cache por CACHE_TTL_SECONDS segundos
    (st.cache_data com ttl=900 -> 15 minutos), evitando leituras
    repetidas a cada interacao do usuario. Quando o cache expira,
    o Streamlit executa a funcao novamente e busca o arquivo atualizado.

    Erros de conexao/leitura (arquivo indisponivel, rede instavel, link
    sem permissao publica etc.) sao convertidos em uma RuntimeError
    generica, que e tratada pela tela principal sem expor detalhes
    tecnicos ao usuario.

    Retorna:
        df (DataFrame): dados prontos para consulta, com colunas
            auxiliares de busca normalizadas (_cnpj_busca, _nf_busca)
            e a coluna de Status calculada.
        carregado_em (datetime): momento em que os dados foram lidos.
    """
    try:
        # O arquivo de origem usa ';' como separador de campos (padrao de
        # exportacao de planilhas em pt-BR), em vez da ',' padrao do CSV.
        df = pd.read_csv(config.CSV_URL, dtype=str, sep=";")
    except Exception as erro:
        raise RuntimeError("Falha ao carregar o arquivo CSV de origem.") from erro

    # Remove espacos extras dos nomes das colunas, caso existam.
    df.columns = [str(c).strip() for c in df.columns]

    # Garante que todas as colunas esperadas existam, mesmo que o arquivo
    # esteja temporariamente sem alguma delas (evita KeyError mais adiante).
    colunas_esperadas = [
        config.COL_CLIENTE_DESTINATARIO,
        config.COL_CNPJ_DESTINATARIO,
        config.COL_NUMERO_NF,
        config.COL_DATA_EMISSAO,
        config.COL_VALOR_MERCADORIA,
        config.COL_DESCRICAO_ULTIMA_OCORRENCIA,
        config.COL_DATA_ULTIMA_OCORRENCIA,
        config.COL_LOCALIZACAO_ATUAL,
        config.COL_PREVISAO_ENTREGA,
        config.COL_DATA_ENTREGA_REALIZADA,
        config.COL_CHAVE_CTE,
        config.COL_DATA_CANCELAMENTO,
    ]
    for coluna in colunas_esperadas:
        if coluna not in df.columns:
            df[coluna] = ""

    # Trata valores nulos como string vazia para simplificar comparacoes.
    df = df.fillna("")

    # Remove espacos em branco (e tabulacoes) das bordas de todas as celulas.
    for coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.strip()

    # Colunas auxiliares normalizadas, usadas apenas para a busca.
    df["_cnpj_busca"] = df[config.COL_CNPJ_DESTINATARIO].apply(somente_numeros)
    df["_nf_busca"] = df[config.COL_NUMERO_NF].apply(formatar_chave_nf)

    # Converte a data de emissao para datetime, para permitir ordenacao
    # do registro mais recente para o mais antigo. Datas invalidas/vazias
    # se tornam NaT e sao tratadas como as mais antigas.
    df["_data_emissao_dt"] = pd.to_datetime(
        df[config.COL_DATA_EMISSAO], dayfirst=True, format="mixed", errors="coerce"
    )

    # Calcula o Status da entrega conforme as regras de negocio:
    #   - Data da Entrega Realizada preenchida  -> "Entregue"
    #   - Data do Cancelamento preenchida       -> "Cancelado"
    #   - Caso contrario                        -> "Em Transporte"
    def calcular_status(linha):
        if linha[config.COL_DATA_ENTREGA_REALIZADA].strip():
            return "Entregue"
        if linha[config.COL_DATA_CANCELAMENTO].strip():
            return "Cancelado"
        return "Em Transporte"

    df["Status"] = df.apply(calcular_status, axis=1)

    carregado_em = datetime.now()
    return df, carregado_em


# ---------------------------------------------------------------------------
# Renderizacao dos resultados
# ---------------------------------------------------------------------------

STATUS_CORES = {
    "Entregue": "#1e7e34",
    "Cancelado": "#b02a37",
    "Em Transporte": "#0d6efd",
}


def renderizar_card(registro: pd.Series) -> None:
    """Renderiza um card visual com os dados de uma entrega encontrada."""
    status = registro["Status"]
    cor_status = STATUS_CORES.get(status, "#6c757d")

    with st.container(border=True):
        col_status, col_nf = st.columns([2, 1])
        with col_status:
            st.markdown(
                f"""
                <span style="
                    background-color:{cor_status};
                    color:white;
                    padding:6px 14px;
                    border-radius:999px;
                    font-weight:600;
                    font-size:0.9rem;
                ">{status}</span>
                """,
                unsafe_allow_html=True,
            )
        with col_nf:
            st.markdown(
                f"**NF:** {texto_ou_padrao(registro[config.COL_NUMERO_NF])}"
            )

        st.markdown(f"#### {texto_ou_padrao(registro[config.COL_CLIENTE_DESTINATARIO])}")

        st.markdown("##### Dados da Nota Fiscal")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"**Data de Emissão:** "
                f"{formatar_data(registro[config.COL_DATA_EMISSAO])}"
            )
        with c2:
            st.markdown(
                f"**Valor da Mercadoria:** "
                f"{formatar_valor_monetario(registro[config.COL_VALOR_MERCADORIA])}"
            )

        st.markdown("##### Última Movimentação")
        st.markdown(
            f"**Última Ocorrência:** "
            f"{texto_ou_padrao(registro[config.COL_DESCRICAO_ULTIMA_OCORRENCIA])}"
        )
        st.markdown(
            f"**Localização Atual:** "
            f"{texto_ou_padrao(registro[config.COL_LOCALIZACAO_ATUAL])}"
        )
        st.markdown(
            f"**Data da Última Ocorrência:** "
            f"{formatar_data(registro[config.COL_DATA_ULTIMA_OCORRENCIA])}"
        )

        st.markdown("##### Previsão e Entrega")
        c5, c6 = st.columns(2)
        with c5:
            st.markdown(
                f"**Previsão de Entrega:** "
                f"{formatar_data(registro[config.COL_PREVISAO_ENTREGA])}"
            )
        with c6:
            st.markdown(
                f"**Data da Entrega Realizada:** "
                f"{formatar_data(registro[config.COL_DATA_ENTREGA_REALIZADA])}"
            )

        st.markdown("##### Identificação do Transporte")
        st.markdown(
            f"**Chave CT-e:** {texto_ou_padrao(registro[config.COL_CHAVE_CTE])}"
        )


# ---------------------------------------------------------------------------
# Interface principal
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def carregar_logo_base64(caminho: str) -> Optional[str]:
    """Abre uma imagem de logo, remove a margem em branco/transparente ao
    redor do conteúdo (autocrop) e retorna uma string base64 em PNG.

    O autocrop e importante porque os arquivos de logo podem ter
    proporcoes de canvas muito diferentes entre si (ex.: uma quase
    quadrada e outra em formato widescreen com bastante espaço vazio).
    Sem o recorte, aplicar a mesma altura fixa nas duas faria uma
    parecer muito menor que a outra. Apos o recorte, ambas passam a
    ocupar visualmente o mesmo peso quando exibidas com a mesma altura.

    Retorna None se o arquivo nao existir, para que a logo seja omitida
    sem gerar erro.
    """
    if not os.path.isfile(caminho):
        return None

    imagem = Image.open(caminho)

    if imagem.mode == "RGBA":
        # Usa o canal alpha para encontrar a area com conteudo visivel.
        bbox = imagem.split()[-1].getbbox()
    else:
        imagem = imagem.convert("RGB")
        fundo_branco = Image.new("RGB", imagem.size, (255, 255, 255))
        bbox = ImageChops.difference(imagem, fundo_branco).getbbox()

    if bbox:
        imagem = imagem.crop(bbox)

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def injetar_estilos():
    """Injeta o CSS global que da a aparencia de cartoes (cards) brancos
    com sombra suave ao cabecalho de logos e ao formulario de consulta,
    alem de centralizar titulo/subtitulo e estilizar o selo de ultima
    atualizacao e a caixa de atencao fixa.

    Centralizar o CSS em uma unica funcao evita repetir blocos <style>
    espalhados pelo codigo e facilita ajustes futuros de aparencia.
    """
    st.markdown(
        """
        <style>
        .logo-card {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 24px;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
            padding: 18px 36px;
            max-width: 460px;
            margin: 0 auto 28px auto;
        }
        .logo-divider {
            width: 1px;
            align-self: stretch;
            background: #e2e2e2;
        }
        .titulo-pagina {
            text-align: center;
            font-weight: 800;
            margin-bottom: 4px;
            /* Streamlit renderiza headings markdown como flex containers
               (para posicionar o icone de link de ancora), por isso
               text-align nao basta: e preciso centralizar via flex. */
            justify-content: center;
        }
        .titulo-pagina [data-testid="stHeaderActionElements"] {
            display: none;
        }
        .subtitulo-pagina {
            text-align: center;
            color: #6c757d;
            margin-bottom: 18px;
        }
        .pill-atualizacao {
            display: flex;
            justify-content: center;
            margin-bottom: 24px;
        }
        .pill-atualizacao span {
            background: #f1f2f4;
            color: #555555;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 0.85rem;
        }
        div[data-testid="stForm"] {
            background: #ffffff;
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
            border: 1px solid #eef0f2;
        }
        .caixa-atencao {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            background: #fdecee;
            border: 1px solid #f8c9ce;
            border-radius: 12px;
            padding: 14px 18px;
            margin-top: 20px;
            color: #8a1c24;
            font-size: 0.9rem;
        }
        .caixa-atencao b {
            color: #c51f2b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_logo():
    """Exibe as logos institucionais lado a lado, dentro de um cartão
    branco arredondado com sombra suave, separadas por uma linha divisória
    vertical, caso os arquivos assets/logo.png e/ou
    assets/logo_fundo_branco.jpg existam. Cada logo ausente é omitida
    individualmente, sem gerar erro para o usuário; se nenhuma existir,
    o cartão inteiro é ocultado.

    Usa HTML/CSS (flexbox) em vez de st.image() porque é necessário
    aplicar altura fixa com largura automática (preservando a proporção
    de cada imagem) e alinhamento vertical centralizado — combinação que
    st.image() não oferece diretamente.
    """
    imagens_base64 = [
        b64
        for b64 in (
            carregar_logo_base64(LOGO_PATH),
            carregar_logo_base64(LOGO_FUNDO_BRANCO_PATH),
        )
        if b64
    ]
    if not imagens_base64:
        return

    tag_imagem = (
        '<img src="data:image/png;base64,{b64}" '
        f'style="height:{ALTURA_LOGO_PX}px; width:auto; max-width:100%; '
        'object-fit:contain;" />'
    )
    divisor = '<div class="logo-divider"></div>'
    conteudo = divisor.join(tag_imagem.format(b64=b64) for b64 in imagens_base64)

    st.markdown(f'<div class="logo-card">{conteudo}</div>', unsafe_allow_html=True)


def renderizar_caixa_atencao():
    """Exibe a caixa fixa de aviso sobre a regra da chave composta,
    sempre visível abaixo do formulário (independente de já ter sido
    feita uma consulta), para deixar a regra clara antes mesmo do erro.
    """
    st.markdown(
        """
        <div class="caixa-atencao">
            ⚠️
            <span><b>Atenção:</b> a consulta somente será realizada quando
            CPF/CNPJ e Número da Nota Fiscal coincidirem.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(
        page_title=config.APP_TITLE,
        page_icon="📦",
        layout="centered",
    )
    injetar_estilos()

    renderizar_logo()
    st.markdown(
        f'<h1 class="titulo-pagina">{config.APP_TITLE}</h1>', unsafe_allow_html=True
    )
    st.markdown(
        f'<p class="subtitulo-pagina">{config.APP_SUBTITLE}</p>',
        unsafe_allow_html=True,
    )

    # Carrega os dados (com cache). Qualquer falha de leitura do CSV
    # (rede instavel, arquivo indisponivel, etc.) e tratada de forma
    # amigavel, sem expor detalhes tecnicos ao usuario final.
    try:
        df, carregado_em = load_data()
        dados_disponiveis = True
    except Exception:
        df, carregado_em = pd.DataFrame(), None
        dados_disponiveis = False

    if not dados_disponiveis:
        st.error(config.MSG_ERRO_CARREGAMENTO)
        renderizar_rodape()
        return

    st.markdown(
        f'<div class="pill-atualizacao"><span>🕒 Última atualização dos dados: '
        f'{carregado_em.strftime("%d/%m/%Y %H:%M")}</span></div>',
        unsafe_allow_html=True,
    )

    with st.form("formulario_consulta"):
        documento_digitado = st.text_input(
            "CPF/CNPJ do Destinatário *",
            placeholder="Ex: 123.456.789-01 ou 12.345.678/0001-99",
            help="Informe o CPF (11 dígitos) ou CNPJ (14 dígitos) do destinatário.",
            icon="🪪",
        )
        numero_nf_digitado = st.text_input(
            "Número da Nota Fiscal *",
            placeholder="Ex: 12345",
            icon="🧾",
        )
        enviado = st.form_submit_button(
            "Consultar", use_container_width=True, type="primary", icon="🔍"
        )

    renderizar_caixa_atencao()

    if not enviado:
        renderizar_rodape()
        return

    # Normaliza os valores digitados antes de qualquer validacao/comparacao.
    documento_numerico = somente_numeros(documento_digitado)
    nf_numerica = formatar_chave_nf(numero_nf_digitado)

    # Validacao de campos obrigatorios. Nunca permitir busca apenas por
    # um dos dois campos: ambos sao exigidos para liberar a consulta.
    if not documento_numerico or not numero_nf_digitado.strip():
        st.warning("Por favor, informe o CPF/CNPJ e o Número da Nota Fiscal.")
        renderizar_rodape()
        return

    if len(documento_numerico) not in (11, 14):
        st.warning("CPF/CNPJ inválido. Informe 11 dígitos (CPF) ou 14 dígitos (CNPJ).")
        renderizar_rodape()
        return

    # Chave composta: so retorna resultado se CPF/CNPJ E Numero da NF
    # coincidirem simultaneamente.
    resultado = df[
        (df["_cnpj_busca"] == documento_numerico)
        & (df["_nf_busca"] == nf_numerica)
    ]

    if resultado.empty:
        st.error(config.MSG_NAO_ENCONTRADO)
        renderizar_rodape()
        return

    # Ordena do registro mais recente para o mais antigo.
    resultado = resultado.sort_values("_data_emissao_dt", ascending=False)

    st.success(f"{len(resultado)} registro(s) encontrado(s).")
    for _, registro in resultado.iterrows():
        renderizar_card(registro)

    renderizar_rodape()


def renderizar_rodape():
    st.divider()
    st.markdown(
        f"<div style='text-align:center; color:#6c757d; font-size:0.85rem;'>"
        f"{config.FOOTER_TEXT}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
