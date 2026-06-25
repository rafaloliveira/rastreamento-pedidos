# app.py
# Aplicacao Streamlit de consulta publica de entregas e notas fiscais.
#
# Fluxo geral:
#   1. Carrega (com cache) os dados do arquivo CSV hospedado no Google Drive.
#   2. Normaliza os campos usados na pesquisa (CNPJ e Numero da NF).
#   3. Exibe um formulario para o usuario informar CNPJ + Numero da NF.
#   4. Filtra os registros pela chave composta (documento + nota fiscal).
#   5. Exibe o(s) resultado(s) em cards, do mais recente para o mais antigo.

import base64
import os
import re
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from typing import Optional

import gdown
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageChops

import config

# Fuso horario de referencia para exibir a data/hora de atualizacao dos
# dados. O servidor onde a aplicacao roda (ex.: Streamlit Cloud) costuma
# operar em UTC, mas o publico-alvo esta no Brasil.
FUSO_HORARIO_BRASIL = ZoneInfo("America/Sao_Paulo")

# Caminhos das logos institucionais. A pasta assets/ e os arquivos sao
# opcionais: se nao existirem, a area correspondente e simplesmente ocultada.
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
LOGO_FUNDO_BRANCO_PATH = os.path.join(ASSETS_DIR, "logo_fundo_branco.jpg")

# Mapeamento de papel declarado pelo usuario para a coluna de CNPJ correspondente.
PAPEL_PARA_COLUNA = {
    "Remetente": config.COL_CNPJ_REMETENTE,
    "Expedidor": config.COL_CNPJ_EXPEDIDOR,
    "Pagador": config.COL_CNPJ_PAGADOR,
    "Destinatário": config.COL_CNPJ_DESTINATARIO,
    "Recebedor": config.COL_CNPJ_RECEBEDOR,
}
PAPEIS = list(PAPEL_PARA_COLUNA.keys())


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
            auxiliares de busca normalizadas (_cnpjs_busca, _nf_busca)
            e a coluna de Status calculada.
        carregado_em (datetime): momento em que os dados foram lidos,
            no fuso horário do Brasil (America/Sao_Paulo), independente
            do fuso horário do servidor onde a aplicação está hospedada.
    """
    try:
        # Baixa o arquivo via gdown (em memoria) em vez de uma URL direta:
        # o arquivo e grande o suficiente para o Google Drive exibir uma
        # pagina de aviso de "virus scan" no lugar do download direto, e o
        # gdown sabe lidar com esse token de confirmacao automaticamente.
        buffer = BytesIO()
        gdown.download(id=config.CSV_DRIVE_FILE_ID, output=buffer, quiet=True)
        buffer.seek(0)

        # O arquivo de origem usa ';' como separador de campos (padrao de
        # exportacao de planilhas em pt-BR), em vez da ',' padrao do CSV, e
        # e salvo em UTF-8 com BOM (utf-8-sig remove o marcador do inicio).
        df = pd.read_csv(buffer, dtype=str, sep=";", encoding="utf-8-sig")
    except Exception as erro:
        raise RuntimeError("Falha ao carregar o arquivo CSV de origem.") from erro

    # Remove espacos extras dos nomes das colunas, caso existam.
    df.columns = [str(c).strip() for c in df.columns]

    # Garante que todas as colunas esperadas existam, mesmo que o arquivo
    # esteja temporariamente sem alguma delas (evita KeyError mais adiante).
    colunas_esperadas = [
        config.COL_CLIENTE_DESTINATARIO,
        *config.COLS_CNPJ_BUSCA,
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

    # Remove espacos em branco (e tabulacoes) das bordas de todas as
    # celulas, alem do residuo de mojibake "Â" que aparece no arquivo de
    # origem (um espaco nao separavel foi salvo como dois bytes UTF-8,
    # 0xC2 0xA0, que decodificados separadamente viram "Â" + espaco; o
    # espaco e removido pelo strip padrao, sobrando o "Â" solto na borda).
    for coluna in df.columns:
        df[coluna] = (
            df[coluna]
            .astype(str)
            .str.replace("\xa0", " ", regex=False)
            .str.strip(" \t\r\nÂ")
        )

    # Colunas auxiliares normalizadas por papel, para busca precisa pelo
    # campo exato correspondente ao papel que o usuario declarou ocupar.
    for col in config.COLS_CNPJ_BUSCA:
        df[f"_norm_{col}"] = df[col].apply(somente_numeros)
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

    carregado_em = datetime.now(FUSO_HORARIO_BRASIL)
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

    Tambem oculta toda a "chrome" nativa do Streamlit (menu hamburguer,
    header, toolbar, botao Deploy, badge "Manage app", footer e icones
    de ancora dos titulos) e remove os paddings padrao do container
    principal, para que a aplicacao pareca um sistema corporativo
    proprio e nao um app Streamlit. Os seletores usam tanto classes
    estaveis (ex.: .stApp) quanto atributos data-testid, que mudam
    menos entre versoes do Streamlit do que classes geradas (ex.: .css-*).

    Centralizar o CSS em uma unica funcao evita repetir blocos <style>
    espalhados pelo codigo e facilita ajustes futuros de aparencia.
    """
    st.markdown(
        """
        <style>
        /* ===================================================================
           1) Remocao da "chrome" nativa do Streamlit
           Cada selecionador abaixo cobre um elemento de identidade visual
           do Streamlit (menu, header, toolbar, badge de deploy, footer e
           icones de ancora). Usar varios seletores redundantes (classe +
           data-testid) e proposital: versoes diferentes do Streamlit
           renomeiam classes internas, mas tendem a manter os atributos
           data-testid mais estaveis, entao a combinacao reduz o risco de
           o elemento "voltar a aparecer" apos uma atualizacao do pacote.
           =================================================================== */

        /* Menu principal (hamburguer) no canto superior direito. */
        #MainMenu { visibility: hidden; display: none; }

        /* Header padrao do Streamlit (faixa no topo da pagina). */
        header[data-testid="stHeader"] { display: none; height: 0; }

        /* Footer padrao ("Made with Streamlit"). */
        footer { visibility: hidden; display: none; }

        /* Toolbar flutuante (canto superior direito: deploy, settings etc.). */
        div[data-testid="stToolbar"] { visibility: hidden; display: none; }
        div[data-testid="stDecoration"] { display: none; }
        div[data-testid="stStatusWidget"] { display: none; }

        /* Botao/badge "Deploy" e badge "Manage app" do Streamlit Cloud. */
        .stDeployButton { display: none; }
        a[href*="streamlit.io"],
        a[data-testid="manage-app-button"] { display: none !important; }

        /* Icones de ancora (link) que aparecem ao lado de cada titulo
           markdown (h1-h4) ao passar o mouse. */
        [data-testid="stHeaderActionElements"] { display: none !important; }
        h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }

        /* Selecionadores defensivos para nomes usados em versoes mais
           recentes/antigas do Streamlit, caso os data-testid acima mudem. */
        [class*="viewerBadge"],
        [data-testid="stAppViewBadge"],
        [data-testid="stAppDeployButton"],
        [data-testid="stBottomBlockContainer"] > div[class*="badge"] {
            display: none !important;
        }

        /* Selo "Hosted with Streamlit" + avatar do criador do app, injetado
           pelo Streamlit Community Cloud como uma camada de chrome por cima
           da aplicacao (geralmente fixo no canto inferior direito). Esse
           badge usa classes geradas com hash (ex.: _profileImage_gzau3_78)
           que mudam a cada build, por isso o seletor usa "contains" ([class
           *="_profileImage_"]) em vez do nome completo da classe. O
           data-testid="appCreatorAvatar" e o atributo mais estavel para
           localizar o avatar; o container "ViewerBadge_*"/"viewerBadge_*" e
           o nome historico usado pelo Streamlit Cloud para o wrapper do selo. */
        img[data-testid="appCreatorAvatar"],
        [class*="_profileImage_"],
        [class*="_lightThemeShadow_"],
        [id^="ViewerBadge_container"],
        [id^="ViewerBadge_link"],
        [class*="viewerBadge_container"],
        [class*="viewerBadge_link"],
        a[href*="streamlit.io/cloud"],
        a[title*="Hosted with Streamlit"],
        a[title*="View app source"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* ===================================================================
           2) Espacamento e aproveitamento vertical da pagina
           Remove o "vao" cinza/vazio que o Streamlit reserva por padrao
           para o header e para o padding superior do bloco principal.
           =================================================================== */
        .stApp { margin-top: 0 !important; }

        div[data-testid="stAppViewContainer"] > section,
        div[data-testid="stAppViewContainer"] {
            padding-top: 0 !important;
        }

        div[data-testid="stMainBlockContainer"],
        div[data-testid="block-container"] {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
        }

        @media (max-width: 768px) {
            div[data-testid="stMainBlockContainer"],
            div[data-testid="block-container"] {
                padding-top: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }

        /* ===================================================================
           3) Aparencia corporativa geral (fundo, tipografia, foco)
           =================================================================== */
        .stApp {
            background: #f5f6f8;
        }

        /* "Zoom out" geral da pagina: reduz o tamanho efetivo de tudo
           dentro do bloco principal (formulario, textos, cards), para que
           mais conteudo caiba na tela sem precisar rolar tanto. A
           propriedade "zoom" recalcula o layout no tamanho reduzido (ao
           contrario de transform: scale, que so encolhe visualmente sem
           reduzir a altura real da pagina). Suportada por Chrome/Edge/
           Safari, que cobrem a grande maioria dos acessos a este portal. */
        div[data-testid="stMainBlockContainer"],
        div[data-testid="block-container"] {
            zoom: 70%;
        }

        html, body, [class*="css"] {
            font-family: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif;
        }

        /* Os campos de CNPJ e Numero da NF ocupam 100% da largura do
           formulario por padrao (comportamento nativo do st.text_input).
           Como o formulario em si ja e razoavelmente largo, isso deixa os
           campos maiores do que o necessario em telas largas. Limitamos o
           wrapper de cada input a uma largura maxima e centralizamos,
           mantendo o input interno ocupando 100% desse wrapper menor. */
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"] {
            max-width: 420px;
            margin: 0 auto;
        }

        /* O botao "Consultar" usa use_container_width=True (para empilhar
           bem em telas estreitas), mas isso o deixa esticado por toda a
           largura do formulario em telas largas. O wrapper do submit
           (stFormSubmitButton) e limitado a uma largura maxima e
           centralizado via margin auto, enquanto o botao interno continua
           ocupando 100% desse wrapper menor. */
        div[data-testid="stFormSubmitButton"] {
            max-width: 240px;
            margin: 0 auto;
        }

        div[data-testid="stForm"] button[kind="primaryFormSubmit"],
        .stButton button[kind="primary"] {
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(13, 110, 253, 0.25);
        }

        @media (max-width: 480px) {
            div[data-testid="stTextInput"],
            div[data-testid="stSelectbox"],
            div[data-testid="stFormSubmitButton"] {
                max-width: 100%;
            }
        }

        div[data-baseweb="input"] {
            border-radius: 10px;
            border: 1px solid #c51f2b;
        }

        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border: 1px solid #c51f2b !important;
        }

        div[data-baseweb="select"] > div:focus-within {
            border-color: #c51f2b !important;
            box-shadow: 0 0 0 1px #c51f2b !important;
        }

        div[data-baseweb="input"]:focus-within {
            border-color: #c51f2b;
            box-shadow: 0 0 0 1px #c51f2b;
        }

        .logo-card {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
            gap: 24px;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
            padding: 18px 32px;
            width: 100%;
            max-width: 500px;
            margin: 0 auto 28px auto;
            box-sizing: border-box;
            overflow: hidden;
        }
        .logo-card img {
            /* height/width "auto" + max-height/max-width preservam a
               proporcao original ao encolher a imagem para caber no
               espaco disponivel (em vez de distorcer o aspecto). */
            height: auto;
            width: auto;
            max-height: 80px;
            max-width: 100%;
            object-fit: contain;
        }
        .logo-divider {
            width: 1px;
            align-self: stretch;
            background: #e2e2e2;
        }
        /* Em telas de celular, reduz a altura das logos e os espacamentos
           do cartao para que ambas caibam confortavelmente dentro do
           fundo branco, sem ultrapassar as bordas. Se ainda assim nao
           houver espaco suficiente, o flex-wrap acima permite que as
           logos quebrem para duas linhas, centralizadas. */
        @media (max-width: 768px) {
            .logo-card {
                gap: 16px;
                padding: 16px 20px;
            }
            .logo-card img {
                max-height: 56px;
            }
            .logo-divider {
                display: none;
            }
        }
        .titulo-pagina {
            text-align: center;
            font-weight: 800;
            font-size: 1.1rem !important;
            margin-bottom: 4px;
            /* Streamlit renderiza headings markdown como flex containers
               (para posicionar o icone de link de ancora), por isso
               text-align nao basta: e preciso centralizar via flex. */
            justify-content: center;
        }
        @media (max-width: 480px) {
            .titulo-pagina {
                font-size: 0.95rem !important;
            }
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
    aplicar altura máxima com largura automática (preservando a
    proporção de cada imagem) e alinhamento vertical centralizado —
    combinação que st.image() não oferece diretamente. O tamanho das
    imagens é controlado inteiramente via CSS (classe .logo-card img,
    em injetar_estilos()), e não por style inline, para que o media
    query de responsividade mobile consiga reduzi-las corretamente.
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

    tag_imagem = '<img src="data:image/png;base64,{b64}" />'
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
            <span><b>Atenção:</b> selecione sua função no transporte,
            informe seu CNPJ/CPF e o Número da Nota Fiscal.
            A busca é feita apenas no campo correspondente ao papel selecionado.</span>
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
        papel_selecionado = st.selectbox(
            "Sou:",
            PAPEIS,
            index=None,
            placeholder="Selecione...",
            help="Selecione sua função neste transporte para que a busca seja feita no campo correto.",
        )
        documento_digitado = st.text_input(
            "CNPJ/CPF *",
            placeholder="Apenas números",
            help=(
                "Informe somente números, sem pontos, barras ou traços. "
                "CNPJ: 14 números. CPF: 11 números (zeros à esquerda são "
                "adicionados automaticamente)."
            ),
            icon="🪪",
            max_chars=14,
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

    # Validacao de campos obrigatorios.
    if papel_selecionado is None:
        st.warning("Por favor, selecione sua função no transporte (Sou:).")
        renderizar_rodape()
        return

    if not documento_digitado.strip() or not numero_nf_digitado.strip():
        st.warning("Por favor, informe o CNPJ/CPF e o Número da Nota Fiscal.")
        renderizar_rodape()
        return

    if not documento_digitado.isdigit():
        st.warning("O CNPJ/CPF deve conter somente números, sem pontos, barras ou traços.")
        renderizar_rodape()
        return

    # CPF tem 11 digitos; a planilha guarda CPFs no campo de CNPJ
    # completando com zeros a esquerda ate chegar a 14 digitos.
    if len(documento_digitado) == 11:
        documento_numerico = documento_digitado.zfill(14)
    else:
        documento_numerico = documento_digitado
    nf_numerica = formatar_chave_nf(numero_nf_digitado)

    if len(documento_numerico) != 14:
        st.warning("CNPJ/CPF inválido. Informe os 14 dígitos do CNPJ ou os 11 dígitos do CPF.")
        renderizar_rodape()
        return

    # Busca precisa: verifica o CNPJ apenas na coluna correspondente ao papel
    # que o usuario declarou (Remetente, Expedidor, Pagador, Destinatario ou
    # Recebedor), eliminando falsos positivos causados por numeros iguais em
    # papeis distintos ou por CPFs que coincidam numericamente com CNPJs.
    coluna_cnpj = PAPEL_PARA_COLUNA[papel_selecionado]
    col_norm = f"_norm_{coluna_cnpj}"
    resultado = df[
        (df[col_norm] == documento_numerico)
        & (df["_nf_busca"] == nf_numerica)
    ]

    if resultado.empty:
        st.error(config.MSG_NAO_ENCONTRADO)
        renderizar_rodape()
        return

    # Ordena do registro mais recente para o mais antigo.
    resultado = resultado.sort_values("_data_emissao_dt", ascending=False)

    # Ancora usada pelo script de rolagem automatica abaixo, para que o
    # usuario veja os resultados sem precisar rolar a tela manualmente
    # (o formulario e os textos acima dos resultados costumam empurra-los
    # para fora da area visivel, especialmente em telas menores).
    st.markdown('<div id="ancora-resultados"></div>', unsafe_allow_html=True)
    st.success(f"{len(resultado)} registro(s) encontrado(s).")
    for _, registro in resultado.iterrows():
        renderizar_card(registro)

    renderizar_rodape()
    rolar_para_resultados()


def rolar_para_resultados():
    """Rola a pagina suavemente até a âncora '#ancora-resultados'.

    Usa components.html (em vez de st.markdown) porque tags <script>
    inseridas via st.markdown(unsafe_allow_html=True) sao removidas pelo
    sanitizador do Streamlit. O componente roda em um iframe isolado, por
    isso o script acessa window.parent.document para alcançar o DOM real
    da página.
    """
    components.html(
        """
        <script>
            const ancora = window.parent.document.getElementById("ancora-resultados");
            if (ancora) {
                ancora.scrollIntoView({behavior: "smooth", block: "start"});
            }
        </script>
        """,
        height=0,
    )


def renderizar_rodape():
    st.divider()
    st.markdown(
        f"<div style='text-align:center; color:#6c757d; font-size:0.85rem;'>"
        f"{config.FOOTER_TEXT}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
