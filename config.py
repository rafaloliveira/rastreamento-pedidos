# config.py
# Arquivo central de configuracoes do projeto.
# Mantem em um unico lugar os parametros que podem precisar de ajuste futuro,
# como a URL da planilha e o tempo de vida do cache.

# ID do arquivo CSV hospedado no Google Drive (extraido da URL de
# compartilhamento). O arquivo precisa estar compartilhado como "Qualquer
# pessoa com o link pode visualizar" para que o download funcione sem
# autenticacao (necessario porque a aplicacao roda no Streamlit Community
# Cloud, sem acesso ao Google Drive local). O download e feito via gdown
# (em vez de uma URL direta) porque o arquivo e grande o suficiente para o
# Google Drive interpor uma pagina de aviso de "virus scan" no lugar do
# download direto.
CSV_DRIVE_FILE_ID = "1eDiIka7vgC2orh4KvBgp95RaktnSCb8V"

# Tempo de vida do cache de dados, em segundos.
# 900 segundos = 15 minutos.
# O arquivo CSV e recarregado automaticamente quando o cache expira,
# evitando leituras excessivas a cada consulta do usuario.
CACHE_TTL_SECONDS = 900

# Textos fixos da interface, centralizados para facilitar manutencao.
APP_TITLE = "Consulta de Entregas"
APP_SUBTITLE = (
    "Informe seu CNPJ e o número da Nota Fiscal para consultar "
    "o status da sua entrega."
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
