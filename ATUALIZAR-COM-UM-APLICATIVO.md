# Sais Blue CRM — um aplicativo para atualizar, iniciar e parar

No servidor Windows, baixe **SaisBlue-Atualizador.exe** e abra o arquivo. Ele usa o Python e o banco que já existem na instalação. Não é necessário reinstalar o CRM, extrair o pacote manualmente ou encerrar terminais.

**Download:** [SaisBlue-Atualizador.exe](https://github.com/wilmezzomo-source/teste_saisblue/raw/refs/heads/crm-windows/desktop/SaisBlue-Atualizador.exe).

1. O aplicativo tenta localizar a instalação que está rodando. Se o campo estiver vazio, clique em **Procurar** e selecione a pasta original do CRM, onde estão `.env` e `.venv`.
2. Clique em **Atualizar e abrir CRM**.
3. Aguarde a conferência do download, parada da aplicação, backup, atualização, validação e reinício. Na primeira ativação do início automático, o Windows pedirá autorização de administrador: clique em **Sim**. Essa permissão é exigida pelo Agendador de Tarefas do Windows. Nenhuma senha será gravada pelo CRM.
4. Confira a mensagem **Início automático e recuperação de falhas ativados**. O navegador abre no endereço já configurado. Se o Windows não autorizar, o CRM inicia normalmente, mas a proteção automática fica pendente; use **Iniciar / reconectar** para tentar ativá-la novamente.

O atalho **Sais Blue CRM** é criado na área de trabalho do usuário do Windows. Nas próximas vezes, abra esse mesmo atalho:

- **Atualizar e abrir CRM:** consulta a versão indicada no repositório autorizado e aplica o pacote automaticamente.
- **Abrir CRM:** abre o navegador no endereço já configurado.
- **Iniciar / reconectar:** inicia a aplicação ou tenta restabelecer a conexão HTTPS.
- **Parar CRM:** encerra somente os processos identificados da instalação selecionada. Essa escolha é mantida após reiniciar o Windows, até você usar **Iniciar / reconectar** ou atualizar novamente.
- **Configurar iPhone e acesso externo:** prepara o app, gera a solicitação para Telium/TI e ativa HTTPS depois de DNS e rede configurados. Atualize e reabra pelo atalho para carregar o novo botão. Veja [IPHONE-E-ACESSO-EXTERNO.md](IPHONE-E-ACESSO-EXTERNO.md).

Depois de concluir, você pode fechar a janela do aplicativo. A partir da versão **2026.11.11.1**, uma tarefa própria desta instalação inicia um monitor com o Windows, sem precisar deixar uma conta conectada. Ele recupera o CRM e o túnel de mensagens após falhas. A tarefa usa a conta Windows que aplicou a atualização, com direitos limitados e sem guardar a senha; a confirmação de administrador é necessária apenas para registrá-la. O servidor precisa permanecer ligado e com internet. A equipe continua acessando pelo navegador na rede da empresa, sem instalar esse aplicativo.

O monitor verifica a aplicação e o agente a cada 30 segundos. Falhas recebem novas tentativas espaçadas de 15, 30, 60, 120, 240 e até 300 segundos, respeitando o ciclo de verificação. Ele não cria processos duplicados, aguarda a atualização e preserva a parada manual. Um processo sem resposta recebe um período de tolerância antes de ser reiniciado. Se o próprio monitor falhar, o Agendador do Windows tenta iniciá-lo novamente após um minuto.

A recuperação não resolve servidor desligado, perda de internet, IP da rede alterado, limite/suspensão da conta ngrok ou credencial Meta expirada. O monitor não altera a URL cadastrada na Meta nem envia mensagens de teste para clientes. O diagnóstico local fica em `.runtime/supervisor.json`, sem tokens ou dados dos leads.

## O que é preservado

Banco, contas, senhas e `.env` permanecem na instalação. O backup do banco e dos arquivos substituídos fica em `backups/atualizacao-*`. O programa confere a integridade SHA-256 do ZIP antes de parar o CRM; usa somente o repositório `wilmezzomo-source/teste_saisblue`. Uma falha de download não interrompe o servidor.

A nova versão é conferida antes de ser considerada pronta. Se a atualização falhar depois da cópia, o programa tenta restaurar os arquivos e o banco do backup e reiniciar a versão anterior; só informa recuperação concluída após verificar a aplicação. Uma falha do disco, de energia ou de permissão pode exigir intervenção; o backup e a mensagem ficam disponíveis para diagnóstico.

Os processos são identificados pelo caminho da instalação, script, PID e instante de criação. O programa não encerra todos os programas Python/ngrok do computador. Se não conseguir comprovar a identidade de um processo que ocupa a porta, interrompe a operação e explica isso na janela. Para processos iniciados por outra conta ou por uma tarefa elevada do Windows, pode ser necessário abrir o aplicativo com **Executar como administrador**; essa exigência vem das permissões do Windows.

## WhatsApp

O conector tenta reutilizar o domínio ngrok já cadastrado na Meta. Credenciais não são pedidas novamente nem enviadas ao GitHub. O retorno de “conexão HTTPS pronta” comprova a verificação do callback e do isolamento das rotas privadas, não a entrega de uma mensagem pela Meta. Se o túnel não puder ser reaberto, a janela informa a pendência e permite tentar **Iniciar / reconectar**. O CRM não publica sua tela de login pelo túnel do WhatsApp.

As melhorias de anúncios, roteiro de qualificação, tags, relatórios, distribuição Chai/Grasi, cadastro manual e acesso restrito por responsável estão incluídas. O administrador original vê todos os cards; atendentes veem apenas os seus. Consulte `OPORTUNIDADES-MANUAIS.md`. Depois da primeira atualização, convide as duas em Equipe e ative o primeiro atendimento em Integrações conforme `ATUALIZACAO-ANUNCIOS-E-QUALIFICACAO.md`.

## Código e manutenção

O código da interface está em `desktop/Updater.cs`; o fluxo de parada, backup e recuperação está em `desktop_worker.py` e `update_windows.py`. O executável usa os componentes .NET Framework do Windows e o Python já instalado; não é assinado com certificado comercial. `desktop/build.py` permite recompilar com o compilador oficial Roslyn e as referências oficiais .NET Framework v4.8.

`windows-release.json` aponta para um commit imutável e o hash do ZIP conferido. Uma atualização do canal só deve acontecer após publicar o commit correspondente e conferir o pacote. O código baixa a versão indicada no canal; não executa instruções arbitrárias presentes no JSON. Testes Windows são executados em máquina isolada pelo workflow `Windows updater`, sem acesso ao servidor da empresa e sem credenciais reais.

A versão do atualizador entregue com 2026.11.09.4 consulta o manifesto com um identificador de consulta e sem cache local, para reduzir a chance de carregar uma versão anterior logo após uma publicação. O ZIP continua fixado por commit e SHA-256 antes de parar a aplicação.
