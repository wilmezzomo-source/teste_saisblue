# Publicar o CRM da Sais Blue em Windows

**Situação:** pacote preparado; instalação não executada no servidor da empresa. Os testes de backend e navegador rodam no ambiente Linux de desenvolvimento. PowerShell, tarefas agendadas, DNS, HTTPS e a conta Meta precisam ser validados no Windows real.

O servidor informado é Windows e o site/e-mails são hospedados pela Telium. Não temos acesso ao servidor, ao painel Telium, ao DNS ou à conta Meta. `crm.saisblue.com.br` é uma sugestão e não um endereço já publicado. O número informado é **+55 54 3443-6405**; não equivale ao Phone Number ID da Meta.

## Decisões com o responsável de TI

- Confirmar versão do Windows, atualização, disponibilidade de Python 3.12+ e acesso administrativo autorizado.
- Definir entre hospedar na empresa ou em uma VPS gerenciada. O plano atual de site/e-mail pode não permitir um processo Python contínuo; consultar a Telium antes.
- Se na empresa: confirmar IP público estável, portas 80/443, firewall, internet e energia. Se houver CGNAT ou restrição de entrada, usar uma hospedagem adequada ou uma solução de publicação aprovada por TI.
- Manter o banco em disco **local** do servidor; nunca colocar o SQLite em uma pasta de rede/SMB. Todos os navegadores usam a mesma aplicação e o mesmo banco central.
- Separar o serviço do CRM dos arquivos internos da empresa. Não disponibilizar RDP, a porta 3000, os arquivos `.env`, o banco ou backups pela internet.
- Configurar um subdomínio para o CRM sem mudar os registros do site, MX e outros registros dos e-mails.

## Primeiro teste pelo usuário

O arquivo `INICIAR-NO-WINDOWS.cmd` chama `setup_windows.py`, que instala dependências na pasta `.venv`, prepara uma configuração local apenas se `.env` não existir e solicita a criação do primeiro administrador. Senhas passam pelo pipe do processo Python, sem ir para argumentos ou arquivos em texto. O navegador abre no endereço configurado e a aplicação funciona enquanto a janela estiver aberta. Requer Python 3.12+ com launcher `py`. O script não instala acesso remoto nem publica portas. O assistente usa simulações locais; desative-as ao publicar. Os passos abaixo são para a instalação persistente com HTTPS.

## Instalação (responsável de TI)

1. Extraia o pacote em `C:\SaisBlueCRM` ou outro caminho local fixo. Não inclua o banco fictício de desenvolvimento.
2. Instale Python 3.12+ oficial com o launcher `py` e Caddy para Windows, em local fixo acessível à conta de serviço.
3. Abra PowerShell no diretório do projeto e execute:

```powershell
.\deploy\windows.ps1 -Action Install
```

O script cria `.venv`, instala Flask/Waitress, cria diretórios de dados/backups e copia `.env.example` para `.env` **sem substituir uma configuração existente**.

4. Edite `.env` como texto, sem aspas nos valores. Ajuste `APP_URL` e `CRM_DOMAIN` ao domínio aprovado. A configuração de exemplo usa produção com HTTPS e simulação desativada. Deixe as chaves da Meta vazias até ter os dados oficiais. Para teste apenas no próprio servidor, pode usar `APP_ENV=development` e `APP_URL=http://127.0.0.1:3000`, mas volte a produção/HTTPS antes de publicar.
5. Execute a verificação e crie o administrador com um e-mail real:

```powershell
.\deploy\windows.ps1 -Action Check
.\deploy\windows.ps1 -Action Admin -Email "EMAIL_REAL_DO_ADMIN" -Name "NOME_DO_ADMIN"
```

A senha é solicitada no terminal (mínimo 12 caracteres). Não existe senha padrão, conta de teste ou cadastro público. Se já existe uma conta com esse e-mail, a criação não a substitui.

6. Aponte o DNS do subdomínio aprovado para o servidor e libere as portas necessárias para HTTPS. Execute em dois terminais de teste:

```powershell
.\deploy\windows.ps1 -Action Run
.\deploy\windows.ps1 -Action Proxy -CaddyPath "C:\CAMINHO_DO_CADDY\caddy.exe"
```

O Waitress atende em `127.0.0.1:3000`. Caddy termina o HTTPS e encaminha as requisições. O backend aceita encaminhamento de IP/protocolo apenas do proxy local. Caddy gerencia os certificados automaticamente quando DNS, acesso e portas estão corretos. Não use o servidor de desenvolvimento Flask em produção.

7. Teste o domínio pelo navegador de outro computador e de um celular fora da rede: certificado válido, login e edição de card. Pare os dois processos de teste antes do passo seguinte para não disputar portas.
8. Em PowerShell elevado, registre o início automático e o backup diário:

```powershell
.\deploy\windows.ps1 -Action RegisterTasks -CaddyPath "C:\CAMINHO_DO_CADDY\caddy.exe"
```

O script registra as tarefas `SaisBlueCRM`, `SaisBlueCRM-HTTPS` e `SaisBlueCRM-Backup` como **LOCAL SERVICE**. Restringe a pasta a conta instaladora, administradores, SYSTEM e LOCAL SERVICE; só `data` e `backups` recebem escrita pela conta de serviço. Revise permissões se os arquivos já tiverem ACLs explícitas. As tarefas de aplicação/proxy iniciam no boot e tentam reiniciar em falha; os dados ficam fora do código. A execução depende das políticas PowerShell locais: siga a política da empresa, sem desabilitá-la globalmente. Não registre a aplicação como SYSTEM/administrador para contornar problemas de acesso.

9. Confirme no Agendador de Tarefas e após reiniciar o Windows que os serviços voltam e o HTTPS funciona. Revise logs do agendador e teste que a conta LOCAL SERVICE consegue salvar dados e certificados.

## Incluir toda a equipe

Entre como administrador, abra **Equipe**, informe e-mail e perfil **Membro**, e gere um link. Compartilhe individualmente por um canal da empresa. O sistema não envia e-mails automaticamente. Cada convite expira em 48 horas e só pode ser usado uma vez. A pessoa define seu nome e senha.

**Todo membro ativo pode ver e alterar todos os cards**, mesmo se houver outro responsável. Pode mudar etapas, valores, responsável e observações, adicionar notas e responder WhatsApp quando conectado. Só administradores gerenciam acessos. É possível desativar uma conta e gerar link de redefinição de senha (válido por uma hora). A desativação ou redefinição revoga sessões anteriores.

Os dados do funil são consultados a cada 5 segundos. Se uma ficha aberta ficar desatualizada, uma gravação conflitante é recusada com aviso. O usuário pode recarregar o card e revisar sua alteração. Isso evita sobrescrever silenciosamente o trabalho de outra pessoa. As alterações são registradas com autor e horário.

## WhatsApp oficial

É necessário descobrir se o número já está no WhatsApp Business Platform. Se estiver apenas no aplicativo, avaliar com a Meta/provedor oficial a modalidade de coexistência suportada ou uma migração planejada. Não desconectar o celular nem migrar o número sem avaliar o impacto no atendimento e a elegibilidade da conta.

No app Meta e na conta WhatsApp Business da empresa:

1. Confirmar titularidade/acesso ao Business Portfolio e cadastrar ou vincular o número.
2. Obter `META_PHONE_NUMBER_ID`, `META_APP_SECRET` e um `META_ACCESS_TOKEN` de sistema com permissões apropriadas. Gerar um valor aleatório forte para `META_VERIFY_TOKEN`. Não compartilhar esses valores no chat, por e-mail aberto ou no repositório; inserir no arquivo protegido do servidor.
3. Verificar a versão suportada da Graph API e ajustar `META_API_VERSION` (padrão configurável `v22.0`).
4. Cadastrar o webhook `https://DOMINIO_APROVADO/webhooks/whatsapp`, o mesmo token de verificação e assinar eventos de mensagens da conta correta.
5. Reiniciar a tarefa da aplicação após mudar credenciais e testar com mensagem real de outro telefone, resposta, confirmação de entrega e um contato vindo de anúncio.

O adaptador filtra o Phone Number ID para não misturar mensagens de outro número; valida assinatura, evita eventos duplicados e registra a origem de anúncio quando a Meta a fornece. Responde texto dentro de 24 horas da última mensagem real do cliente. Mensagens simuladas não abrem essa janela. Fora da janela, o envio é bloqueado: envio por **templates ainda não está implementado**. Áudios, imagens e outros anexos aparecem como indicação de tipo; **download/visualização de mídia ainda não estão implementados**. Custos e regras da Meta/provedor aplicam-se conforme a conta.

O envio registra pedido, aceitação, envio, entrega, leitura ou falha conforme a Meta informa. Em timeout o estado é “Sem confirmação”; não há reenvio automático, para evitar mensagens duplicadas. Verifique o histórico antes de tentar um novo envio. Ainda não houve validação com a conta real.

## Backup e recuperação

A tarefa diária cria backup consistente às 02:00 do relógio do Windows, retendo 30 dias nesta pasta. Confira o fuso de São Paulo no servidor. Para executar manualmente:

```powershell
.\deploy\windows.ps1 -Action Backup
```

Os backups incluem contatos, mensagens, contas e sessões: são confidenciais. Faça cópia criptografada fora do servidor e monitore a execução; backup só local não cobre perda do disco. Antes de operar, teste restauração em cópia isolada. Para restaurar, pare a aplicação e substitua o banco por um backup validado; preserve o banco e arquivos WAL/SHM anteriores em outra pasta e não misture arquivos WAL antigos com o banco restaurado. Reinicie, confira registros e revogue sessões restauradas se necessário.

## Pedido preparado para a Telium / TI (não enviado)

> Precisamos publicar um CRM próprio para a Sais Blue, separado do site e dos e-mails. Temos um servidor Windows interno; também queremos avaliar hospedagem gerenciada. Nosso plano atual permite uma aplicação Python 3.12+ com processo persistente e dados em disco local, proxy HTTPS e webhook público da Meta? Se não, qual opção de VPS/servidor gerenciado atende? Queremos usar um subdomínio como crm.saisblue.com.br sem alterar site/MX. Precisamos de HTTPS válido, backup externo e publicação segura. O pacote usa Flask/Waitress e SQLite para uma única instância. A instalação em Windows está documentada e precisamos de apoio do responsável técnico para acesso, DNS e firewall. Por favor confirmem viabilidade e eventual custo antes de contratar ou alterar o ambiente.
