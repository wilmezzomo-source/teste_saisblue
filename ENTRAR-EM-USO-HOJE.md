Para a atualização atual, use **Sais Blue CRM → Atualizar e abrir CRM**, conforme [OPORTUNIDADES-MANUAIS.md](OPORTUNIDADES-MANUAIS.md). O procedimento abaixo registra a instalação inicial.

# Sais Blue — execução por etapas, com validação

Versão **2026.11.06.4**. Objetivo inicial: equipe usando o CRM na rede da empresa. A integração com o WhatsApp oficial só está concluída quando uma mensagem real entra no CRM e uma resposta chega ao cliente; um token, um número listado ou um retorno `accepted` não comprovam isso.

## 1. Atualizar a instalação que já existe

**No Windows do servidor**, não no Mac usado para acessar a Meta:

1. Pare o CRM com **Ctrl+C** no terminal onde ele roda. Se usa tarefa agendada, pare a tarefa da aplicação com o responsável de TI.
2. Baixe o ZIP atualizado do repositório e **extraia todo o conteúdo em uma pasta nova**.
3. Na pasta nova, abra **ATUALIZAR-NO-WINDOWS.cmd**.
4. Na janela de seleção, escolha a **pasta antiga**, onde estão `.env`, `.venv`, `data` e `INICIAR-NO-WINDOWS.cmd`.
5. Aguarde o resultado. O atualizador faz backup do banco e do código substituído e preserva a configuração, o banco e os acessos. Se ele disser que o CRM continua rodando, pare o processo e repita a atualização. Se houver falha nas dependências, não inicie até corrigir a etapa.
6. Na **pasta antiga**, abra **INICIAR-NO-WINDOWS.cmd**.

**Validação:** o CRM abre com a logo SB enviada, conserva os contatos existentes e mostra `2026.11.06.3` no rodapé após o login. Se houver erro, pare aqui e informe a mensagem; não reinstale nem crie outro banco.

## 2. Validar o uso pela equipe

1. Com o CRM rodando, na pasta antiga execute **VALIDAR-INSTALACAO.cmd**.
2. Ele deve mostrar aplicação e banco acessíveis e login obrigatório. Use o endereço que o relatório informa; o IP informado anteriormente foi **192.168.0.219**.
3. Em **outro computador da mesma rede**, abra **http://192.168.0.219:3000**. Se o relatório apontar outro IP, use o do relatório, não este exemplo anterior.
4. Se não abrir: na pasta antiga do servidor, execute **ATIVAR-REDE-E-WHATSAPP.cmd** como administrador, escolha **1**, selecione a placa Ethernet, reinicie o CRM e repita o teste. A regra vale só para a sub-rede e perfis Private/Domain; rede Public/segmentada exige revisão com TI.
5. No servidor, abra o CRM pelo **mesmo endereço da equipe**, entre como administrador e crie um convite em **Equipe**. Envie individualmente à pessoa. Ela define sua senha; não precisa instalar Python ou o CRM.
6. Uma pessoa entra no outro computador, cria um contato fictício com cidade/UF e move o card. Confira a alteração no servidor. Cada atendente vê e edita apenas os cards atribuídos à própria conta. Somente o administrador original vê todas as oportunidades e as sem responsável.
7. Confira também Instagram, ficha e Mapa. Depois use dados reais apenas no escopo aprovado pela empresa.

**Validação:** duas pessoas, em computadores distintos, veem e editam o mesmo card. A aplicação precisa permanecer rodando no servidor; fechar o navegador não a encerra, fechar o terminal manual pode encerrá-la. Para início automático e backups agendados, seguir `deploy/INSTALAR-WINDOWS.md` com TI.

**Limite atual:** o acesso LAN por HTTP é um piloto sem criptografia. HTTPS para proteger credenciais e dados continua pendente. Não encaminhar a porta 3000 no roteador. Banco SQLite permanece em disco local, não em pasta compartilhada.

## 3. Diagnosticar o número OFICIAL, uma vez

O número escolhido é **Sais Blue – Willian, +55 54 3443-6405**, Phone Number ID mostrado pela Meta **321395016679053**. A referência de conta observada foi **1398958113869625**. O programa verificará se essa referência permite listar o número; a existência do perfil no painel não comprova isso.

1. Na Meta, use um token válido autorizado para a conta oficial **Sais Blue – Willian**. Se o token tiver sido exposto, revogue o exposto e use um novo. Tokens ficam no computador da empresa, não no chat.
2. Na pasta antiga do servidor Windows, abra **DIAGNOSTICAR-WHATSAPP.cmd**.
3. Cole o token quando solicitado. Ele **não aparece durante a digitação**. Pressione Enter.
4. Aguarde o resumo. O programa faz apenas consultas GET: não envia mensagens, não registra/migra o número, não altera a conta e não grava o token em arquivo.
5. Compartilhe **DIAGNOSTICO-WHATSAPP-RESULTADO.txt**, que contém somente identificação/códigos/resultado, não o token.

**Decisões a partir do resultado:**

- `TOKEN_INVALIDO` / erro 190: renovar o token com a autorização correta. Esse é um problema de credencial, não de entrega.
- `SEM_ACESSO_CONFIRMADO`: revisar a permissão do usuário/app para o número oficial. Não tentar registrar, migrar ou desconectar o aplicativo como solução.
- `ACESSO_DE_LEITURA_OK`: o token acessa o número; ainda faltam habilitação e validação do canal, assinatura do app e webhook.
- Campo opcional `unknown`: a API não confirmou esse atributo. Não interpretar como coexistência habilitada ou indisponível.
- `platform_type=CLOUD_API`: identifica a plataforma retornada; não é prova de funcionamento ponta a ponta.

**Validação:** obter um diagnóstico do número oficial, não outro envio de `+1 555...`. O erro 131000 que apareceu pertenceu ao teste da Meta; a causa específica desse erro não foi informada. O histórico do CRM agora armazena códigos de erros reais recebidos pelo próprio CRM.

## 4. Habilitação oficial, HTTPS e webhook

Após o fluxo QR oficial, o número do Willian passou a aparecer como Inscrito no app. Para o piloto HTTPS com ngrok autorizado pelo usuário, siga agora `CONECTAR-WHATSAPP-HOJE.md`. Esse roteiro detalha a configuração local e a validação da URL; a inscrição não substitui o teste final de mensagens.


Para terminar a integração mantendo o aplicativo WhatsApp Business, é necessário um processo oficial de onboarding compatível com coexistência e elegível para esta conta. A inscrição foi observada no painel, mas a entrega real continua pendente de validação. Dependendo do caminho oferecido pela Meta, pode ser necessário um provedor habilitado. Isso pode exigir análise, prazo e contratação; nenhum desses passos foi realizado pelo pacote.

Depois de confirmar a habilitação e a autorização da conta/app:

1. Disponibilizar **uma URL pública HTTPS para o webhook**, com acesso autorizado à infraestrutura. O IP privado 192.168.0.219 não é acessível à Meta pela internet.
2. O modelo `deploy/Caddyfile-whatsapp-only` permite publicar só `/webhooks/whatsapp`, mantendo o CRM na rede local. DNS, certificado e firewall precisam de configuração efetiva no servidor/Telium. O domínio `crm.saisblue.com.br` foi apenas sugerido; não está automaticamente criado por este pacote.
3. Configurar no servidor Phone Number ID oficial, token de operação, App Secret e token de verificação. Usar o assistente existente somente com os dados confirmados da conta oficial.
4. Cadastrar/verificar a URL do webhook no app, assinar os eventos `messages` e confirmar que o app está associado à conta correta. Cumprir os requisitos de publicação exibidos pela Meta antes de receber dados de produção.
5. Usar um token de operação adequado, com as permissões e ciclo de vida necessários; o token temporário do teste não é uma configuração definitiva.

**Validação:** verificação GET do webhook aprovada, assinatura de mensagens configurada e eventos reais recebidos pelo endpoint do servidor.

## 5. Teste final com um colega

1. Um colega envia mensagem ao **+55 54 3443-6405**.
2. O contato e a mensagem aparecem no CRM; contato sem cidade é marcado como pendente.
3. A equipe preenche cidade/UF e responde pela ficha dentro da janela de 24h.
4. O colega confirma que recebeu; o histórico apresenta a confirmação informada pela Meta.
5. O colega entra pelo anúncio e envia mensagem. Conferir cadastro/histórico e origem quando fornecida pela Meta.

**Concluído:** somente quando esse percurso funciona. Templates fora da janela de 24h e visualização de mídia ainda não estão disponíveis nesta versão. Se o webhook informa `failed`, consultar o código registrado no histórico; não repetir envios indefinidamente.
