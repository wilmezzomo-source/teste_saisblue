# Sais Blue CRM — um aplicativo para atualizar, iniciar e parar

No servidor Windows, baixe **SaisBlue-Atualizador.exe** e abra o arquivo. Ele usa o Python e o banco que já existem na instalação. Não é necessário reinstalar o CRM, extrair o pacote manualmente ou encerrar terminais.

1. O aplicativo tenta localizar a instalação que está rodando. Se o campo estiver vazio, clique em **Procurar** e selecione a pasta original do CRM, onde estão `.env` e `.venv`.
2. Clique em **Atualizar e abrir CRM**.
3. Aguarde a conferência do download, parada da aplicação, backup, atualização, validação e reinício. O navegador abre no endereço já configurado.

O atalho **Sais Blue CRM** é criado na área de trabalho do usuário do Windows. Nas próximas vezes, abra esse mesmo atalho:

- **Atualizar e abrir CRM:** consulta a versão indicada no repositório autorizado e aplica o pacote automaticamente.
- **Abrir CRM:** abre o navegador no endereço já configurado.
- **Iniciar / reconectar:** inicia a aplicação ou tenta restabelecer a conexão HTTPS.
- **Parar CRM:** encerra somente os processos identificados da instalação selecionada.

Depois de concluir, você pode fechar a janela do aplicativo: o CRM e o conector continuam em segundo plano. O servidor Windows precisa permanecer ligado. Este aplicativo não instala um serviço novo nem configura início automático ao reiniciar o Windows; tarefas existentes da aplicação são respeitadas. A equipe continua acessando pelo navegador na rede da empresa, sem instalar esse aplicativo.

## O que é preservado

Banco, contas, senhas e `.env` permanecem na instalação. O backup do banco e dos arquivos substituídos fica em `backups/atualizacao-*`. O programa confere a integridade SHA-256 do ZIP antes de parar o CRM; usa somente o repositório `wilmezzomo-source/teste_saisblue`. Uma falha de download não interrompe o servidor.

A nova versão é conferida antes de ser considerada pronta. Se a atualização falhar depois da cópia, o programa tenta restaurar os arquivos e o banco do backup e reiniciar a versão anterior; só informa recuperação concluída após verificar a aplicação. Uma falha do disco, de energia ou de permissão pode exigir intervenção; o backup e a mensagem ficam disponíveis para diagnóstico.

Os processos são identificados pelo caminho da instalação, script, PID e instante de criação. O programa não encerra todos os programas Python/ngrok do computador. Se não conseguir comprovar a identidade de um processo que ocupa a porta, interrompe a operação e explica isso na janela. Para processos iniciados por outra conta ou por uma tarefa elevada do Windows, pode ser necessário abrir o aplicativo com **Executar como administrador**; essa exigência vem das permissões do Windows.

## WhatsApp

O conector tenta reutilizar o domínio ngrok já cadastrado na Meta. Credenciais não são pedidas novamente nem enviadas ao GitHub. O retorno de “conexão HTTPS pronta” comprova a verificação do callback e do isolamento das rotas privadas, não a entrega de uma mensagem pela Meta. Se o túnel não puder ser reaberto, a janela informa a pendência e permite tentar **Iniciar / reconectar**. O CRM não publica sua tela de login pelo túnel do WhatsApp.

As melhorias de anúncios, roteiro de qualificação, tags, relatórios e distribuição Chai/Grasi estão incluídas. Depois da primeira atualização, convide as duas em Equipe e ative o primeiro atendimento em Integrações conforme `ATUALIZACAO-ANUNCIOS-E-QUALIFICACAO.md`.

## Código e manutenção

O código da interface está em `desktop/Updater.cs`; o fluxo de parada, backup e recuperação está em `desktop_worker.py` e `update_windows.py`. O executável usa os componentes .NET Framework do Windows e o Python já instalado; não é assinado com certificado comercial. `desktop/build.py` permite recompilar com o compilador oficial Roslyn e as referências oficiais .NET Framework v4.8.

`windows-release.json` aponta para um commit imutável e o hash do ZIP conferido. Uma atualização do canal só deve acontecer após publicar o commit correspondente e conferir o pacote. O código baixa a versão indicada no canal; não executa instruções arbitrárias presentes no JSON. Testes Windows são executados em máquina isolada pelo workflow `Windows updater`, sem acesso ao servidor da empresa e sem credenciais reais.
