# log_consultas.py
# Registra o historico de consultas feitas no portal publico em uma
# planilha Google Sheets (config.LOG_SHEET_ID), para acompanhamento
# interno direto na planilha.
#
# O acesso a planilha e feito via service account (credenciais em
# st.secrets["gcp_service_account"]). Falhas ao registrar uma consulta
# (ex.: planilha fora do ar) nunca devem quebrar a consulta publica, por
# isso registrar_consulta() nunca propaga exceptions - apenas imprime o
# traceback nos logs para diagnostico.

import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import requests
import streamlit as st
from google.oauth2.service_account import Credentials

import config

FUSO_HORARIO_BRASIL = ZoneInfo("America/Sao_Paulo")

_ESCOPOS = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Timeout curto para a consulta de geolocalizacao: essa chamada acontece
# dentro do fluxo de busca do usuario publico, entao uma demora aqui nao
# pode travar a resposta da consulta principal.
_TIMEOUT_GEOLOCALIZACAO_SEGUNDOS = 2

CABECALHO = [
    "Data/Hora",
    "Papel",
    "CNPJ/CPF Consultado",
    "Número da NF",
    "Resultado",
    "Registros Encontrados",
    "IP Público",
    "Cidade",
    "Estado",
    "País",
]


@st.cache_resource(show_spinner=False)
def _obter_planilha():
    """Autentica com a service account e retorna a worksheet de log.

    Cria a aba e o cabecalho automaticamente caso ainda nao existam.
    """
    credenciais = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=_ESCOPOS
    )
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open_by_key(config.LOG_SHEET_ID)

    try:
        aba = planilha.worksheet(config.LOG_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        aba = planilha.add_worksheet(
            title=config.LOG_WORKSHEET_NAME, rows=1000, cols=len(CABECALHO)
        )
        aba.append_row(CABECALHO)

    return aba


def _obter_localizacao(ip: str) -> tuple[str, str, str]:
    """Consulta um servico gratuito de geolocalizacao por IP e retorna
    (cidade, estado, pais). Em caso de falha, IP privado/local ou timeout,
    retorna "-" nos tres campos em vez de propagar a excecao.
    """
    try:
        resposta = requests.get(
            f"https://ipapi.co/{ip}/json/", timeout=_TIMEOUT_GEOLOCALIZACAO_SEGUNDOS
        )
        dados = resposta.json()
        if dados.get("error"):
            return "-", "-", "-"
        return (
            dados.get("city") or "-",
            dados.get("region") or "-",
            dados.get("country_name") or "-",
        )
    except Exception:
        return "-", "-", "-"


def registrar_consulta(
    papel: str,
    documento: str,
    numero_nf: str,
    encontrado: bool,
    quantidade: int,
    ip: str,
) -> None:
    """Adiciona uma linha ao log com os dados da consulta realizada."""
    try:
        aba = _obter_planilha()
        agora = datetime.now(FUSO_HORARIO_BRASIL).strftime("%d/%m/%Y %H:%M:%S")
        resultado = "Encontrado" if encontrado else "Não encontrado"
        cidade, estado, pais = _obter_localizacao(ip) if ip else ("-", "-", "-")
        aba.append_row(
            [
                agora,
                papel,
                documento,
                numero_nf,
                resultado,
                quantidade,
                ip or "-",
                cidade,
                estado,
                pais,
            ]
        )
    except Exception:
        # Nunca deixa uma falha de log quebrar a consulta publica, mas
        # imprime o traceback (visivel nos logs do Streamlit Cloud /
        # terminal local) para permitir diagnostico.
        traceback.print_exc()
