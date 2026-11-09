# Sais Blue CRM — equipe e WhatsApp

## Aplicativo único para atualizar — 2026.11.09.6

No Windows, use **SaisBlue-Atualizador.exe**: detecta a instalação, baixa e confere o pacote, para somente os processos do CRM, faz backup, atualiza e reinicia em segundo plano. Cria um atalho com opções de abrir, iniciar/reconectar e parar. Veja [ATUALIZAR-COM-UM-APLICATIVO.md](ATUALIZAR-COM-UM-APLICATIVO.md). O aplicativo usa o Python e o banco já instalados, sem extrair ZIP manualmente. Inclui os ajustes de qualificação e tags da versão anterior.

[Baixar o aplicativo para Windows](https://github.com/wilmezzomo-source/teste_saisblue/raw/refs/heads/crm-windows/desktop/SaisBlue-Atualizador.exe). O canal `windows-release.json` fixa a versão 2026.11.09.6, com commit imutável e integridade SHA-256 conferida. A execução dos testes nativos depende da disponibilidade do GitHub Actions; não confundir publicação do pacote com teste no servidor da empresa; a aplicação no servidor da empresa é feita pelo próprio aplicativo, sob a conta Windows que opera o CRM.

Versão própria para funil comercial e atendimento. O administrador original vê todos os cards, inclusive os sem responsável. Atendentes veem e editam apenas os atribuídos às próprias contas e podem cadastrar oportunidades manuais para si. O administrador gerencia acessos e transferências. Dados centralizados em SQLite, com autenticação Flask e execução por Waitress em Windows ou Linux.

**Estado real:** o usuário confirmou recebimento e resposta no WhatsApp oficial, além do primeiro atendimento automático de leads de anúncio no servidor. A versão **2026.11.09.6** entrega o app instalável no iPhone, Web Push e o assistente de HTTPS; precisa ser aplicada pelo atualizador no Windows. O DNS, a rede da empresa e a entrega real na tela bloqueada ainda dependem de ativação e validação com Telium/TI. Veja [VALIDACAO-IPHONE.md](VALIDACAO-IPHONE.md) para os testes concluídos e os limites.

## Qualificação e retomadas — 2026.11.09.6

Sem opção ATENDENTE ou limite de duas respostas. Perfil, cidade e UF são acumulados entre mensagens, mantendo o card na coluna atual ao qualificar, atribuir ou assumir. Dados válidos do catálogo alimentam a localização e o perfil. Todo Lojista vai para Chai; Revenda de RS/SC também. Demais Revendas e todo Consumidor Final vão para Grasi.

Lembretes: intervalos de 5, 10, 30 e 60 minutos após cada envio, e uma última tentativa 23h50 após a última mensagem do cliente. O prazo usa o horário assinado da mensagem recebida; sair/reiniciar o servidor não zera os registros. Sem template ou envio após 24h. Leia [QUALIFICACAO-E-RETOMADAS.md](QUALIFICACAO-E-RETOMADAS.md).

## iPhone e notificações na tela bloqueada — 2026.11.09.6

App instalável pelo Safari, com ícone da Sais Blue. **Avisos → Ativar notificações do aparelho** permite Web Push, inclusive com o app fechado. Requer HTTPS público, iOS 16.4+, instalação na tela inicial e permissão concedida no próprio iPhone. Cada dispositivo é vinculado à conta autenticada; o envio e a abertura conferem a atribuição atual da oportunidade. O aviso bloqueado contém apenas texto genérico, sem nome ou telefone do cliente. Existe teste agendado para 10 segundos. O serviço de envio faz parte do processo iniciado por `launch.py`; iniciar apenas o Flask de desenvolvimento não executa esse serviço.

No aplicativo Windows, **Configurar iPhone e acesso externo** abre o assistente: preparar chave local e solicitação à Telium/TI, ativar Caddy/HTTPS após DNS e roteador, e diagnosticar. O código não possui acesso administrativo à Telium ou ao roteador da empresa. O acesso externo só estará confirmado depois de abrir o domínio em 4G/5G e realizar o teste no aparelho. Consulte [IPHONE-E-ACESSO-EXTERNO.md](IPHONE-E-ACESSO-EXTERNO.md).

## Nomes e avisos — 2026.11.09.6

A ficha oferece **Editar nome**, inclusive antes de completar cidade/UF. A correção fica no histórico e não é substituída pelo nome de perfil nas mensagens seguintes do WhatsApp. Os avisos de novas oportunidades ficam em **Avisos**. O administrador recebe novas entradas; cada atendente recebe apenas contatos atribuídos à própria conta. **Ativar avisos com som** libera um toque neste navegador; o CRM precisa permanecer aberto. Consulte [NOMES-E-AVISOS.md](NOMES-E-AVISOS.md).

## Atalho WhatsApp, filtros e cards — 2026.11.09.6

A ficha oferece **Chamar no WhatsApp** para abrir a conversa pelo número cadastrado, no aplicativo ou Web conforme o aparelho. O administrador pode combinar **Responsável** e **Perfil** no topo do CRM. A seleção vale no funil, contatos, atendimento, mapa e indicadores. **Todos os responsáveis** remove apenas o filtro de responsável; **Sem responsável** mostra as oportunidades ainda sem conta atribuída. O filtro de perfil continua independente. Atendentes mantêm acesso apenas às próprias oportunidades. Os previews mostram somente as etiquetas de perfil e responsável, sem origem ou situação da qualificação. O administrador também pode excluir um card da ficha e recuperá-lo pela Lixeira.

## Anúncios, qualificação, tags e distribuição — 2026.11.06.4

Consulte [ATUALIZACAO-ANUNCIOS-E-QUALIFICACAO.md](ATUALIZACAO-ANUNCIOS-E-QUALIFICACAO.md) para atualizar sem reinstalar, dar acesso à equipe e ativar o roteiro.

- Novos contatos somente com origem de anúncio identificada pela Meta; continuações dos leads admitidos permanecem no histórico. Cadastros anteriores são preservados. Nova oportunidade permite inclusão manual explícita, com origem Manual e sem iniciar o robô. Apenas as próximas mensagens desse telefone são admitidas, além dos leads de anúncios.
- Roteiro fixo opcional no WhatsApp para Lojista/Revenda/Consumidor Final e cidade/UF, com respostas persistidas, fila durável e pausa para atendimento humano. Ativar em Integrações após escolher as contas ativas da equipe.
- Todo Lojista e Revenda de RS/SC → Chai. Revenda dos demais estados e todo Consumidor Final → Grasi.
- Tag de perfil, filtro compartilhado entre as visões e resultados separados por perfil. Assumir/encaminhar atendimento pausa o roteiro.
- Etapa Proposta enviada removida; cards antigos nela migram para Negociação com auditoria.


## Política de privacidade para publicação do app

Páginas estáticas em `docs/`, com o contato confirmado da empresa, política específica do CRM e instruções de exclusão. Consulte `PUBLICAR-POLITICA-META.md`: revisar o texto, ativar GitHub Pages na branch `crm-windows` e pasta `/docs`, verificar as URLs públicas e então cadastrar na Meta. O commit não ativa Pages nem publica o app Meta automaticamente. Não exige atualizar o servidor Windows.

## Piloto de webhook HTTPS — 2026.11.06.3

Veja `CONECTAR-WHATSAPP-HOJE.md`: conector ngrok autorizado para teste, com gateway somente para o callback, verificação do número/app e validação de desafio e isolamento. Novos comandos usam o Python existente; o atualizador também não depende do launcher `py`. Não foi executado com a conta ngrok/Meta real, e não é uma implantação persistente de produção.

## Correção de mapa 2026.11.06.2

O mapa inicia com cartografia local e pins, sem depender de tiles externos. Ruas OpenStreetMap são opcionais, com política de Referer apropriada e retorno ao mapa local em falha. Veja `CORRECAO-MAPA.md` para aplicar sem reinstalar ou alterar banco/configuração.

## Localização e mapa

Cidade/UF obrigatórias nos cadastros manuais, Instagram e aba Mapa com pins por município e filtros por UF/etapa. A migração preserva o banco; contatos antigos e mensagens WhatsApp sem cidade ficam sinalizados como pendentes. Confira `AJUSTES-LOCALIZACAO.md` para o fluxo, atualização Windows, fontes cartográficas e limites. A versão em preparação usa a logo original e as fontes Montserrat/Instrument Serif do site oficial; incluída na versão 2026.11.06.1.

## Entrada em uso

Siga `ENTRAR-EM-USO-HOJE.md` por etapas: atualizar com backup, validar o acesso da equipe, consultar o número oficial na Meta e só então configurar HTTPS/webhook e validar envio/recebimento reais. `VALIDAR-INSTALACAO.cmd` faz a checagem local; `DIAGNOSTICAR-WHATSAPP.cmd` consulta o número oficial sem enviar ou registrar nada. Os relatórios gerados não contêm tokens e não entram no Git. Erros recebidos da Meta agora ficam com código e orientação no histórico da mensagem.

## Funcionalidades

- Login individual, senha com scrypt, sessão de 12 horas com cookie HttpOnly e CSRF; Secure em produção.
- Convites de uso único, validade de 48h; redefinição de senha por link de 1h; desativação de usuários e revogação de sessões.
- Atendentes podem alterar etapa, valor, perfil e observações e adicionar notas somente nas próprias oportunidades. Apenas o administrador original altera responsáveis e acessa cards de toda a equipe ou sem responsável.
- Verificação de versão para impedir sobrescrita por edições simultâneas; sincronização do funil a cada 5 segundos; histórico com autor e alterações.
- Cadastro automático por telefone no webhook, verificação HMAC, filtro do número receptor, deduplicação de eventos e dados do anúncio quando enviados pela Meta.
- Adaptador oficial para responder texto na janela de 24h, identificador de pedido contra reenvio duplicado, estados de envio e atualizações de entrega/leitura.
- Backup consistente do SQLite e kit de instalação Windows com tarefas de aplicação, HTTPS e backup diário.

## Acesso na rede interna e configuração da Meta

Para atualizar uma instalação que já está funcionando, veja `REDE-E-WHATSAPP.txt`. O novo assistente `ATIVAR-REDE-E-WHATSAPP.cmd` configura o IP privado e uma regra de firewall restrita à sub-rede, preservando banco e credenciais. Usa HTTP para validação na rede local; HTTPS continua necessário para proteger o acesso em operação. Execute na pasta original do CRM, como administrador para a regra do Windows. O assistente também verifica as credenciais diretamente na Meta e confere o número +55 54 3443-6405 antes de salvá-las. Não substitui a publicação/assinatura de um webhook HTTPS.

Para manter o CRM restrito à rede interna e receber eventos reais da Meta, há o modelo `deploy/Caddyfile-whatsapp-only`, que expõe apenas `/webhooks/whatsapp`. DNS, certificado, proxy e conta Meta ainda precisam ser configurados no ambiente real. O comando Windows `Proxy` usa esse modelo quando `APP_ENV=lan`.

## Instalar no servidor Windows

Para um primeiro teste no próprio Windows, extraia o pacote e abra `INICIAR-NO-WINDOWS.cmd`: o assistente instala as dependências, solicita nome/e-mail/senha e abre o CRM local. Requer Python 3.12+ com launcher `py`. Não configura domínio ou WhatsApp e não instala acesso remoto. Veja `COMECE-AQUI.txt`.

Para publicação e início automático, siga [deploy/INSTALAR-WINDOWS.md](deploy/INSTALAR-WINDOWS.md). O documento inclui os comandos, requisitos de DNS/HTTPS, cadastro do administrador, acesso da equipe, conexão Meta e um pedido pronto para encaminhar à Telium/TI.

Ainda é necessário acesso autorizado ao servidor, domínio/HTTPS e credenciais oficiais da Meta. O telefone informado (+55 54 3443-6405) é apenas referência de negócio, não uma credencial ou identificador da API. Não foram feitas mudanças no site, e-mails ou DNS.

## Atualizar e acessar a instalação existente

Não é necessário reinstalar o CRM a cada versão. Veja `COMO-ATUALIZAR-E-ACESSAR.txt`. Nesta versão, `ATUALIZAR-NO-WINDOWS.cmd` poderá ser executado da pasta nova extraída para selecionar a instalação antiga, fazer backup e atualizar somente o código/dependências. Usuários usam o navegador; somente o servidor Windows executa o programa. Logo/fontes e o atualizador foram testados localmente e incluídos na versão 2026.11.06.1; a execução no Windows da empresa ainda deve ser validada.

## Desenvolvimento local

Python 3.12+:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Crie `.env` a partir de `.env.example` e, para testar localmente, use `APP_ENV=development`, `APP_URL=http://127.0.0.1:3000`, `CRM_DB=data/crm.sqlite3` e, se desejar simulações, `ALLOW_SIMULATION=1`. No Windows use `.venv\Scripts\python.exe`.

```bash
.venv/bin/python launch.py check
.venv/bin/python launch.py admin --email EMAIL_REAL --name NOME_REAL
.venv/bin/python launch.py serve
```

O comando de administrador solicita a senha sem exibi-la. Abra http://127.0.0.1:3000. Convide membros em **Equipe**. Não há envio automático de convites por e-mail. Os dados do protótipo anterior são migrados por adição de colunas, sem apagar contatos ou mensagens; faça backup antes de atualizar. A configuração de exemplo usa um banco novo em `data/`; para migrar um banco anterior, copie-o consistentemente e configure `CRM_DB` para esse arquivo.

## Testes

```bash
.venv/bin/python -m unittest -v
node --check public/app.js
node --check public/auth.js
node test_ui.cjs
```

O teste de navegador requer Playwright e Chromium (disponíveis no ambiente de desenvolvimento). Ele sobe sua própria instância temporária em loopback na porta 3001, com contas e senhas efêmeras, e apaga o banco ao terminar; não cria contas na aplicação principal. Verifica dois usuários, convite, edição por membro, conflito entre fichas abertas, histórico, notas, persistência, navegação, logout e viewport de celular. Usa `.venv/bin/python` e `/usr/bin/chromium`; para outro ambiente ajuste o executável Python do teste e/ou `CHROMIUM_PATH`.

Os testes do servidor cobrem autenticação, CSRF, autorização, convites, bloqueio de acesso, limitação de login, conflito concorrente, migração, webhook, idempotência de envio e timeout. As imagens `preview*.png` são capturas dessa instância temporária de testes.

## Limites e operação

Uma única instância de aplicação/banco em disco local. Não usar SQLite em compartilhamento de rede nem escalar para múltiplos servidores sem migrar para um banco adequado. O polling e a consulta de histórico completa são apropriados para validação/equipe pequena; volume alto requer paginação, processamento em fila e monitoramento. O pacote não configura infraestrutura sozinho e não foi certificado no Windows da empresa. Definir políticas de retenção/LGPD e testar recuperação de backup antes de usar dados reais.

WhatsApp: sem templates fora da janela de 24h e sem download/exibição de mídia nesta versão. Configuração de credenciais não comprova conexão. É necessário testar recebimento, resposta e entrega com a conta real após publicação. Simulação não abre janela de envio. A distribuição por perfil e estado e o roteiro fixo de qualificação estão disponíveis. Não há IA generativa, importação de histórico antigo ou sincronização dos envios feitos no aplicativo por eventos de eco.

## Referência DeskcommCRM

Análise inicial do README, licença e manifesto de https://github.com/melgarafael/DeskcommCRM no commit `3f16949cabb69222da9356b2a453d5eb67d9b0f1`. Licença MIT, com suporte documentado a Meta Cloud API, Next.js e Supabase. A cópia está em `/workspace/deskcomm-reference`. Esta aplicação foi escrita de forma independente e não é um fork nem uma auditoria do projeto original.
