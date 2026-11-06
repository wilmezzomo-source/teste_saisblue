# Política de privacidade — requisito de publicação da Meta

O site saisblue.com.br foi consultado e contém um aviso breve no rodapé sobre o formulário comercial. Ele não descreve todo o tratamento de conversas e acessos no CRM. Foram preparadas páginas estáticas específicas em `docs/`, para publicar no GitHub Pages sem alterar o site principal, o DNS, os e-mails, o servidor Windows ou o túnel do webhook.

O contato **willian@saisblue.com.br** foi confirmado pelo usuário para solicitações de acesso/correção/exclusão. O texto descreve o funcionamento atual: cadastros, mensagens, município/UF, Instagram informado, dados de anúncio recebidos da Meta, usuários da equipe, notas e histórico; banco local; Meta/WhatsApp e piloto ngrok; mapa local e camada opcional; exclusão por solicitação e sem promessa de prazo automático inexistente. Não declara certificação jurídica ou implementação de rotinas que o código não tem.

## Revisar e ativar

1. Revise `docs/REVISAO-PRIVACIDADE.md` e confirme que as práticas descritas correspondem à operação da Sais Blue. Corrigir qualquer diferença antes de cadastrar a página como política oficial do app. A política deve ser mantida conforme a operação evoluir.
2. Abra **Settings → Pages** no repositório `wilmezzomo-source/teste_saisblue`.
3. Em **Build and deployment → Source**, selecione **Deploy from a branch**.
4. Escolha a branch **crm-windows** e a pasta **/docs**. Clique em **Save**.
5. Aguarde o deploy do GitHub Pages concluir. **A publicação do commit não ativa Pages sozinha.**
6. Abra em janela anônima:
   - `https://wilmezzomo-source.github.io/teste_saisblue/privacidade.html`
   - `https://wilmezzomo-source.github.io/teste_saisblue/exclusao-dados.html`
7. Só use as URLs na Meta depois de ambas abrirem publicamente, com conteúdo e sem login. Um 404 indica que a publicação ainda não está ativa ou falhou; confira a execução Pages no GitHub antes de prosseguir.

## Cadastrar na Meta

No app **Sais Blue CRM**, clique em **Ir para as configurações do app** na pendência de publicação:

- **URL da Política de Privacidade**: URL pública validada da página `privacidade.html`.
- Se houver campo para **Exclusão de dados do usuário**, escolha a modalidade **URL de instruções de exclusão** e use `exclusao-dados.html`. Esta é uma instrução manual, não um callback automatizado de exclusão.
- Salve e retorne a **Publicar**.

Confira os demais requisitos que a Meta apresentar no caso de uso WhatsApp. A política é uma pendência identificada na tela; a inclusão dela não garante, por si só, aprovação ou publicação do aplicativo. Após a Meta mostrar publicado/permitir produção, valide uma mensagem real entrando no CRM e a resposta chegando ao outro telefone.

GitHub Pages hospeda apenas documentos públicos dessa pasta. Não inclui `.env`, tokens, banco ou dados dos clientes. Não exige reinstalação no servidor Windows.
