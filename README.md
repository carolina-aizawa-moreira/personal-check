# Personal Check — documentos de reembolso

Agente Python de uso pessoal para uma pasta do Google Drive. Não usa API de IA paga. A execução local evita custo de hospedagem; APIs Google dependem das cotas da sua conta/projeto. O computador precisa estar ligado para executar o processamento.

## O que esta versão faz

- Inspeciona recursivamente a pasta configurada, sem seguir atalhos para fora dela.
- Usa categorias existentes e regras configuráveis. Propõe nomes `AAAA-MM-DD_categoria_tipo_ID.pdf`; o ID evita colisões. A data deve ser revisada quando houver várias datas no documento.
- Lê texto de PDFs e converte JPEG, PNG, TIFF, WebP e BMP em PDF. PDFs digitalizados sem texto e imagens dependem do nome e da pasta; OCR ainda não foi implementado. Documentos Office/Google Docs e outros formatos não são processados.
- Cria **cópias normalizadas**, preservando os originais. A primeira versão não move, exclui ou substitui documentos originais.
- Cria uma planilha e registra data, categoria, tipo, profissional, valor solicitado e link. Profissional e valor exigem preenchimento no plano; não são inferidos nesta versão. Status, valor recebido e datas de solicitação/pagamento são campos manuais e preservados ao atualizar.
- Processa automaticamente apenas nomes com data válida e `recibo` ou `nota fiscal`, dentro da categoria esperada, sem classificação conflitante. Outros casos precisam de aprovação no plano.
- Reaplicar o mesmo plano reutiliza as cópias marcadas pelo agente e atualiza a mesma linha da planilha. Execute apenas um processo por vez. Se o original mudar, gere um novo plano; a versão anterior continua preservada. Documentos duplicados com IDs distintos não são deduplicados por conteúdo.

## Instalação

Use Python 3.11+ e uv. No checkout existente, sem criar worktrees:

```sh
UV_CACHE_DIR=/workspace/.cache/uv uv sync --frozen --extra test
.venv/bin/python -m pytest -q
```

Em seu computador, use `uv sync --frozen --extra test` sem a variável de cache do ambiente em nuvem.

## Conectar sua conta Google

1. No Google Cloud Console, crie um projeto e habilite **Google Drive API** e **Google Sheets API**.
2. Configure a tela de consentimento OAuth para uso pessoal e adicione sua conta como usuário de teste. Em modo de teste, o Google pode expirar a autorização e exigir novo login.
3. Crie um cliente OAuth do tipo **Aplicativo para computador**. Salve o JSON baixado em `.secrets/client_secret.json`, apenas na sua máquina. Não publique nem envie credenciais no chat.
4. Execute `.venv/bin/reembolso login` em seu computador. Abra o endereço mostrado no navegador e autorize; o retorno usa uma porta local. Esse login não deve ser executado em um servidor remoto sem acesso ao navegador e ao callback local.

A autorização pede acesso ao Drive e às planilhas porque a pasta já existe. O escopo OAuth é amplo; o código restringe o processamento à raiz e categorias configuradas. Credenciais e planos ficam em caminhos ignorados pelo Git. Não há conexão Google comprovada neste ambiente em nuvem.

## Preparação e execução

```sh
cp config.example.json config.json
.venv/bin/reembolso folders
```

Informe o ID da sua pasta em `root_folder_id` no arquivo local `config.json`. O comando lista nomes/IDs das pastas sem modificar o Drive. Edite `categories` e `rules` em `config.json` com as categorias reais. As categorias de exemplo **não foram inspecionadas nem confirmadas**.

Crie a planilha uma única vez (ou informe o ID de uma planilha existente e escolha uma aba exclusiva):

```sh
.venv/bin/reembolso create-sheet
.venv/bin/reembolso scan --plan plano.json
.venv/bin/reembolso apply --plan plano.json --auto-clear
```

`scan` só lê os arquivos e salva propostas localmente. `apply --auto-clear` cria cópias e atualiza a planilha nos casos claros; não basta apenas gerar o plano. Para os demais, revise os itens do JSON, preencha `date`, `category`, `destination_id`, `name`, `provider` e `amount`, e marque `approved: true` apenas nos documentos corretos. Reaplique o mesmo plano para concluir os aprovados e recuperar uma atualização de planilha que falhou após criar a cópia.

Use nomes diferentes para novos planos: o agente não sobrescreve revisões existentes. Mantenha os planos privados: podem conter nomes e dados de saúde. O conteúdo dos documentos vai apenas para as APIs Google já utilizadas pelo seu Drive; não é enviado a um modelo de IA.

## Automatização periódica

Esta versão é uma ferramenta de linha de comando, sem serviço permanente ou notificações. Pode ser agendada no computador com cron/Agendador de Tarefas: execute `scan` com um caminho de plano novo e depois `apply --auto-clear` nesse mesmo caminho, sempre no diretório do projeto. Guarde os planos com casos pendentes para revisão. Não agende execuções sobrepostas.

## Validação e limites

Os testes locais cobrem datas inválidas, classificação ambígua, seleção automática conservadora, conversão de imagens e TIFF multipágina, preservação de PDF e valores textuais da planilha. A integração real com sua pasta e a planilha exige OAuth e ainda deve ser validada com uma amostra após a conexão. Esta ferramenta controla documentos; não verifica aprovação pelo convênio nem solicita reembolso por você.
