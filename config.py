# config.py
# Arquivo central de configuracoes do projeto.
# Mantem em um unico lugar os parametros que podem precisar de ajuste futuro,
# como a view de dados e o tempo de vida do cache.

# View do banco (Supabase) lida pelo portal: bi.v_rastreio_portal, com as
# colunas usadas pelo app e os ultimos 120 dias de emissao, atualizada a cada
# ~20 min pelas extracoes. As credenciais ficam em st.secrets["supabase"]
# (host, port, dbname, user, password), nunca neste arquivo. Nao ha fonte
# alternativa: se o banco falhar, o portal mostra MSG_ERRO_CARREGAMENTO.
SUPABASE_VIEW = "bi.v_rastreio_portal"

# Tempo de vida do cache de dados, em segundos.
# 900 segundos = 15 minutos.
# Os dados sao relidos do banco automaticamente quando o cache expira,
# evitando leituras excessivas a cada consulta do usuario.
CACHE_TTL_SECONDS = 900

# Textos fixos da interface, centralizados para facilitar manutencao.
APP_TITLE = "Consulta de Entregas"
APP_SUBTITLE = (
    "Selecione sua função, informe seu CNPJ/CPF e o número da Nota Fiscal "
    "para consultar o status da sua entrega."
)
FOOTER_TEXT = "Portal de Consulta de Entregas"

MSG_NAO_ENCONTRADO = (
    "Não foi possível localizar a nota fiscal informada. "
    "Verifique os dados digitados."
)
MSG_ERRO_CARREGAMENTO = (
    "Não foi possível carregar os dados neste momento. "
    "Tente novamente em alguns minutos."
)

# Nomes das colunas esperadas no arquivo CSV de origem.
# Centralizar aqui facilita ajustar caso o arquivo mude algum cabecalho.
COL_CLIENTE_DESTINATARIO = "Cliente Destinatario"
COL_CNPJ_DESTINATARIO = "CNPJ Destinatario"
COL_CNPJ_PAGADOR = "CNPJ Pagador"
COL_CNPJ_REMETENTE = "CNPJ Remetente"
COL_CNPJ_EXPEDIDOR = "CNPJ Expedidor"
COL_CNPJ_RECEBEDOR = "CNPJ Recebedor"

# Colunas de CNPJ usadas na busca: a consulta retorna resultado se o CNPJ
# informado coincidir com QUALQUER uma delas (remetente, expedidor,
# pagador, destinatario ou recebedor), permitindo que qualquer um dos
# envolvidos no transporte consulte usando apenas o proprio CNPJ.
COLS_CNPJ_BUSCA = [
    COL_CNPJ_REMETENTE,
    COL_CNPJ_EXPEDIDOR,
    COL_CNPJ_PAGADOR,
    COL_CNPJ_DESTINATARIO,
    COL_CNPJ_RECEBEDOR,
]

# ---------------------------------------------------------------------------
# Log de consultas
# ---------------------------------------------------------------------------
# ID da planilha Google Sheets (extraido da URL) onde cada consulta feita no
# portal publico e registrada como uma nova linha. A planilha precisa estar
# compartilhada com o e-mail da service account (ver README) com permissao
# de Editor. O acompanhamento e feito diretamente na planilha.
LOG_SHEET_ID = "173FRQsh-_vRTWm9jgOUNvig0rJn0tZksG50IEgWKZFU"

# Nome da aba dentro da planilha onde as linhas de log sao adicionadas.
LOG_WORKSHEET_NAME = "Consultas"

COL_NUMERO_NF = "Numero da Nota Fiscal"
COL_DATA_EMISSAO = "Data de Emissao"
COL_VALOR_MERCADORIA = "Valor da Mercadoria"
COL_DESCRICAO_ULTIMA_OCORRENCIA = "Descricao da Ultima Ocorrencia"
COL_DATA_ULTIMA_OCORRENCIA = "Data da Ultima Ocorrencia"
COL_LOCALIZACAO_ATUAL = "Localizacao Atual"
COL_PREVISAO_ENTREGA = "Previsao de Entrega"
COL_DATA_ENTREGA_REALIZADA = "Data da Entrega Realizada"
COL_CHAVE_CTE = "Chave CT-e"
COL_DATA_CANCELAMENTO = "Data do Cancelamento"
