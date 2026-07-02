# Portal de Consulta de Entregas

Aplicação Streamlit para consulta pública de entregas e notas fiscais de
transporte, a partir de uma chave composta por **CPF/CNPJ do destinatário**
e **Número da Nota Fiscal**.

## Estrutura do projeto

```
rastreamento-pedidos-ssw/
├── app.py                  # Aplicação Streamlit (interface + lógica de consulta)
├── config.py               # Configurações centrais (URL do CSV, textos, TTL do cache)
├── requirements.txt        # Dependências do projeto
├── assets/
│   ├── logo.png             # Logo institucional (opcional)
│   └── logo_fundo_branco.jpg # Segunda logo institucional (opcional)
├── .streamlit/
│   └── config.toml         # Tema visual da aplicação
└── README.md
```

## Instalação

1. Tenha o Python 3.9+ instalado.
2. Crie um ambiente virtual (opcional, mas recomendado):
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Linux/Mac
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Execução

```bash
streamlit run app.py
```

A aplicação abrirá automaticamente no navegador (geralmente em
`http://localhost:8501`).

## Como funciona a consulta

O usuário informa dois campos obrigatórios:

- **CPF/CNPJ do Destinatário** — aceita CPF (11 dígitos) ou CNPJ (14
  dígitos), com ou sem máscara (pontos, barras e traços são removidos
  automaticamente).
- **Número da Nota Fiscal** — aceita números com ou sem zeros à esquerda
  (ex.: `00012345` e `12345` são equivalentes).

A consulta só retorna resultado quando **ambos os campos coincidem**
simultaneamente com um registro da planilha (chave composta). Não é
possível pesquisar apenas por CPF/CNPJ ou apenas por Nota Fiscal.

Se houver mais de um registro para a mesma combinação, todos são
exibidos, ordenados do mais recente para o mais antigo (pela Data de
Emissão).

### Status da entrega

O status é calculado automaticamente a partir das datas da planilha:

| Condição                                  | Status         |
|--------------------------------------------|----------------|
| `Data da Entrega Realizada` preenchida     | Entregue       |
| `Data do Cancelamento` preenchida          | Cancelado      |
| Nenhuma das anteriores                     | Em Transporte  |

## Integração com o arquivo CSV (Google Drive)

Os dados são lidos diretamente de um arquivo CSV hospedado no Google
Drive, configurado em `config.py` na variável `CSV_URL`:

```
https://drive.google.com/uc?export=download&id=<ID_DO_ARQUIVO>
```

A aplicação não escreve no arquivo — apenas lê os dados para exibição.

**Importante:** o arquivo precisa estar com permissão de
compartilhamento "Qualquer pessoa com o link pode visualizar" para que o
download funcione sem autenticação. Caso contrário, o Google Drive
retorna uma página de login em vez do CSV, e a aplicação exibirá a
mensagem de erro de carregamento.

**Formato do arquivo:** o CSV utiliza `;` (ponto e vírgula) como
separador de campos — padrão comum em exportações de planilha em
pt-BR. Essa configuração está em `pd.read_csv(..., sep=";")`, dentro de
`load_data()` em `app.py`. Se o arquivo de origem mudar para vírgula,
ajuste o parâmetro `sep` nessa chamada.

### Colunas esperadas no arquivo CSV

- `Cliente Destinatario`
- `CNPJ Destinatario`
- `Numero da Nota Fiscal`
- `Data de Emissao`
- `Valor da Mercadoria`
- `Descricao da Ultima Ocorrencia`
- `Data da Ultima Ocorrencia`
- `Localizacao Atual`
- `Previsao de Entrega`
- `Data da Entrega Realizada`
- `Chave CT-e`
- `Data do Cancelamento`

Se algum cabeçalho mudar, ajuste o nome correspondente em `config.py`
(constantes `COL_*`).

## Logo institucional

A aplicação carrega automaticamente até duas logos, exibidas lado a lado,
alinhadas verticalmente pelo centro e centralizadas no topo da página,
acima do título:

- `assets/logo.png`
- `assets/logo_fundo_branco.jpg`

- Antes de exibir, cada imagem passa por um **autocrop**: a margem em
  branco/transparente ao redor do conteúdo é removida (função
  `carregar_logo_base64()` em `app.py`). Isso é necessário porque os
  arquivos de origem costumam ter proporções de canvas bem diferentes
  (ex.: uma quase quadrada, outra em formato widescreen com bastante
  espaço vazio) — sem o recorte, aplicar a mesma altura faria uma logo
  parecer bem menor que a outra.
- O tamanho das logos é controlado inteiramente via CSS (classe
  `.logo-card img`, dentro de `injetar_estilos()` em `app.py`) usando
  `max-height` + `max-width: 100%` com `width`/`height: auto`, em vez de
  um tamanho fixo em pixels. Isso preserva a proporção original de cada
  imagem e permite que ela encolha proporcionalmente quando o espaço
  disponível é menor (responsivo), em vez de distorcer ou ultrapassar
  o cartão.
- Há espaçamento horizontal (`gap`) entre as logos.
- **Responsividade mobile:** em telas com largura até 768px, um media
  query reduz a altura máxima das logos (de 80px para 56px) e os
  espaçamentos do cartão, e oculta a linha divisória. O cartão de logos
  sempre ocupa `width: 100%` (até um `max-width` máximo) com
  `box-sizing: border-box`, garantindo que nunca ultrapasse a largura da
  tela. Se mesmo assim não houver espaço suficiente para as duas logos
  lado a lado (telas muito estreitas, ex. 320px), o `flex-wrap` permite
  que elas quebrem para duas linhas, sempre centralizadas e totalmente
  contidas dentro do cartão branco — testado em 320px, 414px, 768px,
  1024px e 1440px de largura.
- Caso um dos arquivos não exista, apenas aquela logo é omitida — a
  outra continua sendo exibida normalmente. Se nenhum dos dois
  arquivos existir, a área de logos é ocultada por completo, sem gerar
  nenhum erro.
- A implementação usa HTML/CSS (`st.markdown` com `unsafe_allow_html`)
  em vez de `st.image()`, pois é necessário combinar altura
  máxima + largura automática + alinhamento vertical centralizado +
  media queries — algo que `st.image()` não permite diretamente.

Para adicionar suas logos, basta colocar os arquivos `logo.png` e/ou
`logo_fundo_branco.jpg` dentro da pasta `assets/`.

## Identidade visual

A interface segue um layout em cartões (cards) brancos com sombra suave
sobre um fundo cinza claro, e usa a cor vermelha da marca ClickLog
(`#E30713`) como cor primária — configurada em `.streamlit/config.toml`
(`primaryColor`) e usada no botão "Consultar" e nos detalhes de
destaque.

Toda a estilização customizada (cartões, selo de última atualização,
caixa de atenção, centralização do título) está concentrada na função
`injetar_estilos()` em `app.py`, que injeta um único bloco `<style>` no
início da página. Para ajustar cores, espaçamentos ou bordas, edite essa
função.

## Cache e performance

A função `load_data()` em `app.py` é decorada com:

```python
@st.cache_data(ttl=config.CACHE_TTL_SECONDS)  # 900 segundos = 15 minutos
def load_data():
    ...
```

Isso significa que:

- O arquivo CSV só é lido do Google Drive uma vez a cada 15 minutos
  (não a cada interação do usuário).
- Isso garante que os dados exibidos nunca fiquem desatualizados por
  muito tempo, sem sobrecarregar o Google Drive com downloads repetidos.
- Quando o cache expira, a próxima consulta dispara automaticamente uma
  nova leitura e atualiza os dados.

A interface exibe o horário da última leitura realizada pela aplicação:

```
Última atualização dos dados: DD/MM/AAAA HH:MM
```

Esse horário é sempre calculado no fuso horário do Brasil
(`America/Sao_Paulo`, via `zoneinfo`), independente do fuso horário do
servidor onde a aplicação estiver hospedada (servidores de hospedagem
costumam operar em UTC). Por isso, o `requirements.txt` inclui o pacote
`tzdata`, necessário para que o `zoneinfo` funcione em ambientes que não
possuem o banco de fusos horários do sistema operacional instalado
(comum em imagens Docker mínimas e no Windows).

## Tratamento e normalização dos dados

A função `somente_numeros()` usa expressão regular (`\D` → remove tudo
que não é dígito) para normalizar:

- O CPF/CNPJ digitado pelo usuário.
- O Número da Nota Fiscal digitado pelo usuário.
- A coluna `CNPJ Destinatario` do CSV.
- A coluna `Numero da Nota Fiscal` do CSV.

Isso resolve inconsistências comuns no arquivo, como:

```
56900847000187Â   →  56900847000187
56.900.847/0001-87 →  56900847000187
```

Para o número da nota fiscal, zeros à esquerda também são removidos antes
da comparação (`00012345` e `12345` tornam-se equivalentes).

## Segurança da consulta

- A busca exige **sempre** os dois campos (CPF/CNPJ + Nota Fiscal).
- Não é informado ao usuário qual campo específico está incorreto em
  caso de erro — apenas uma mensagem genérica.
- Erros técnicos (exceptions, stack traces) nunca são exibidos na tela;
  qualquer falha de carregamento dos dados resulta em uma mensagem
  amigável.

## Manutenção futura

- **Trocar o arquivo CSV de origem:** altere `CSV_URL` em `config.py`.
- **Alterar o tempo de cache:** altere `CACHE_TTL_SECONDS` em
  `config.py`.
- **Adicionar/renomear colunas:** ajuste as constantes `COL_*` em
  `config.py` e, se necessário, a lógica de exibição em `renderizar_card()`
  e o cálculo de status em `calcular_status()`, ambos em `app.py`.
- **Alterar textos da interface:** ajuste as constantes de texto
  (`APP_TITLE`, `APP_SUBTITLE`, `FOOTER_TEXT`, mensagens de erro) em
  `config.py`.
- **Alterar o visual:** edite `.streamlit/config.toml`.

## Log de consultas

Toda consulta feita no portal público (`app.py`), encontrada ou não, chama
`registrar_consulta()` em `log_consultas.py`, que adiciona uma linha a uma
planilha do Google Sheets: data/hora, papel selecionado, CNPJ/CPF
consultado, número da NF, se foi encontrado, quantos registros retornaram,
IP público de quem consultou e a localização aproximada (cidade, estado e
país) obtida a partir desse IP. O acompanhamento é feito diretamente na
planilha — não há uma área separada dentro do app para isso.

IP e localização são obtidos pelo **próprio navegador do cliente**
(função `obter_info_visitante()` em `app.py`, usando o pacote
`streamlit-js-eval`), que chama o serviço gratuito
[ipwho.is](https://ipwho.is/) via JavaScript e retorna o resultado para o
Python. Isso é necessário porque o backend do Streamlit Community Cloud
roda atrás de um proxy reverso e só enxerga o IP interno do proxy (ex.:
faixas `10.x.x.x` ou `192.168.x.x`), nunca o IP público real de quem
acessa — tanto `st.context.ip_address` quanto o cabeçalho
`X-Forwarded-For` retornaram endereços privados nos testes. A chamada só
acontece uma vez por sessão do navegador (o resultado fica em
`st.session_state`), não a cada consulta.

**Limitação conhecida:** como a chamada é feita pelo navegador do cliente,
bloqueadores de anúncio/rastreadores (ex.: uBlock Origin) ou redes
corporativas com proxy/firewall restritivo podem impedir a resolução de
DNS do serviço de geolocalização (`net::ERR_NAME_NOT_RESOLVED` no console
do navegador). Isso é best-effort: quando bloqueado, os campos de
IP/localização ficam "-", sem impedir o registro da consulta nem afetar a
resposta ao usuário. Não há como garantir 100% de preenchimento.

**Atenção (LGPD):** IP público e localização geográfica são considerados
dado pessoal, mesmo sem nome ou documento associado. Antes de usar isso
para indicadores, avalie se é necessário informar aos usuários do portal
que a consulta é registrada para fins de auditoria/indicadores internos.

Falhas ao gravar o log (planilha indisponível, credencial expirada etc.)
são silenciadas — nunca impedem o usuário público de ver o resultado da
sua consulta.

### Configuração necessária (antes de usar em produção)

1. **Crie uma planilha Google Sheets** para armazenar o log e copie o ID
   dela (a parte da URL entre `/d/` e `/edit`).
2. Cole esse ID em `config.py`, na constante `LOG_SHEET_ID`.
3. **Crie uma service account** no
   [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts),
   ative a API do Google Sheets (e do Google Drive) para o projeto, e gere
   uma chave JSON.
4. **Compartilhe a planilha** criada no passo 1 com o e-mail
   `client_email` da service account, com permissão de **Editor**.
5. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`
   e preencha `[gcp_service_account]` com os campos do arquivo JSON
   baixado no passo 3.
6. Em produção (Streamlit Community Cloud), esses mesmos valores devem ser
   colados em **App settings → Secrets** (o arquivo `secrets.toml` local
   nunca é commitado — está no `.gitignore`).

A aba (`config.LOG_WORKSHEET_NAME`, padrão `"Consultas"`) e o cabeçalho são
criados automaticamente na planilha na primeira consulta registrada, caso
ainda não existam.

## Solução de problemas

**A aplicação exibe "Não foi possível carregar os dados neste momento."**
- Verifique se o arquivo no Google Drive ainda está com link de
  compartilhamento público ("qualquer pessoa com o link pode
  visualizar"). Se não estiver, o Drive retorna uma página de login em
  vez do CSV e a leitura falha.
- Verifique a conexão com a internet.
- Confirme que a URL em `config.py` ainda está correta (o ID do arquivo
  não pode ter mudado).

**A consulta não encontra notas que existem no arquivo.**
- Verifique se as colunas `CNPJ Destinatario` e `Numero da Nota Fiscal`
  estão preenchidas corretamente no CSV.
- Confirme que o nome das colunas no arquivo corresponde exatamente ao
  configurado em `config.py` (sensível a espaços e acentuação).

**Os dados exibidos estão desatualizados.**
- Lembre-se que o cache dura até 15 minutos. Aguarde a expiração do
  cache ou reinicie a aplicação (`streamlit run app.py`) para forçar uma
  nova leitura imediata.

**Erro ao instalar dependências.**
- Confirme a versão do Python (`python --version`, recomendado 3.9+).
- Atualize o `pip` antes de instalar: `pip install --upgrade pip`.
