# fonte_supabase.py
# Leitura dos dados de rastreamento direto do banco (Supabase/Postgres).
#
# A role usada pelo portal (app_rastreio) so tem SELECT em UMA view
# (bi.v_rastreio_portal), com as colunas que o app usa e os ultimos 120 dias
# de emissao. As credenciais ficam em st.secrets["supabase"], nunca no codigo.
#
# A conexao e criptografada e a cadeia de certificados e verificada com a CA
# publica do Supabase (certs/supabase-prod-ca-2021.crt). O nome do host nao e
# conferido porque o pooler responde com um certificado emitido para outro
# nome dentro da mesma CA.

import os
import ssl

import pandas as pd
import pg8000.dbapi

CA_PADRAO = os.path.join(os.path.dirname(__file__), "certs", "supabase-prod-ca-2021.crt")


def _contexto_ssl(ca_path: str) -> ssl.SSLContext:
    contexto = ssl.create_default_context(cafile=ca_path)
    contexto.check_hostname = False
    return contexto


def carregar(credenciais, view: str, ca_path: str = CA_PADRAO) -> pd.DataFrame:
    """Le a view inteira e devolve um DataFrame com os nomes de coluna originais.

    credenciais: mapeamento com host, port, dbname, user e password.
    Valores nulos permanecem como None (o app os converte para string vazia).
    """
    conexao = pg8000.dbapi.connect(
        user=credenciais["user"],
        password=credenciais["password"],
        host=credenciais["host"],
        port=int(credenciais.get("port", 5432)),
        database=credenciais.get("dbname", "postgres"),
        ssl_context=_contexto_ssl(ca_path),
        timeout=30,
    )
    try:
        cursor = conexao.cursor()
        cursor.execute(f"select * from {view}")
        colunas = [c[0] for c in cursor.description]
        linhas = cursor.fetchall()
    finally:
        conexao.close()
    return pd.DataFrame(linhas, columns=colunas)
