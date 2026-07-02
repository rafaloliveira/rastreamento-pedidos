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
import streamlit as st
from google.oauth2.service_account import Credentials

import config

FUSO_HORARIO_BRASIL = ZoneInfo("America/Sao_Paulo")

_ESCOPOS = [
    "https://www.googleapis.com/auth/spreadsheets",
]

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


def registrar_consulta(
    papel: str,
    documento: str,
    numero_nf: str,
    encontrado: bool,
    quantidade: int,
    info_visitante: dict,
) -> None:
    """Adiciona uma linha ao log com os dados da consulta realizada.

    info_visitante vem de obter_info_visitante() (app.py) - IP e
    geolocalizacao resolvidos pelo proprio navegador do cliente, ja que o
    backend do Streamlit Community Cloud so enxerga o IP interno do proxy.
    """
    try:
        aba = _obter_planilha()
        agora = datetime.now(FUSO_HORARIO_BRASIL).strftime("%d/%m/%Y %H:%M:%S")
        resultado = "Encontrado" if encontrado else "Não encontrado"
        aba.append_row(
            [
                agora,
                papel,
                documento,
                numero_nf,
                resultado,
                quantidade,
                info_visitante.get("ip") or "-",
                info_visitante.get("city") or "-",
                info_visitante.get("region") or "-",
                info_visitante.get("country") or "-",
            ]
        )
    except Exception:
        # Nunca deixa uma falha de log quebrar a consulta publica, mas
        # imprime o traceback (visivel nos logs do Streamlit Cloud /
        # terminal local) para permitir diagnostico.
        traceback.print_exc()
