# App Sais Blue CRM no iPhone

Esta atualização entrega o aplicativo instalável e o envio de avisos na tela bloqueada. O endereço planejado é **https://crm.saisblue.com.br**. A Telium ainda precisa configurar o DNS; ela hospedar site/e-mail não significa que o servidor Windows já possa ser acessado pela internet.

## 1. Atualizar e preparar no servidor

No **Sais Blue CRM**, clique em **Atualizar e abrir CRM**. Abra novamente pelo atalho para carregar a nova versão do aplicativo Windows. Clique em **Configurar iPhone e acesso externo** e escolha **1**. O assistente gera a chave de notificações uma única vez, preserva as credenciais Meta e abre `SOLICITACAO-TELIUM.txt`.

Encaminhe esse texto à Telium e a quem cuida da rede da empresa. A Telium cria o registro A de `crm.saisblue.com.br` com o IP público confirmado da empresa. A TI/provedor verifica CGNAT, reserva `192.168.0.219` e encaminha somente TCP 80/443 para esse servidor. Não alterar site, e-mails, MX ou nameservers. Não encaminhar 3000, 3002 ou 2019.

Se houver CGNAT ou impedimento de entrada, a arquitetura precisa mudar: solicitar IP público ao provedor ou hospedagem de servidor adequada. Não contratar um serviço pago antes de aprovar o custo. O ngrok atual continua exclusivo para eventos do WhatsApp; seu endereço não abre o CRM.

## 2. Ativar HTTPS após a rede estar pronta

Abra **Configurar iPhone e acesso externo → 2**. Aceite a elevação solicitada pelo próprio Windows. O assistente baixa Caddy 2.11.9 do repositório oficial, confere SHA-512, prepara certificados automáticos e uma tarefa `SaisBlueCRM-HTTPS-…` para iniciar com o Windows. A regra de firewall permite somente esse programa nas portas 80/443. Não encerra serviços que já ocupem essas portas.

Clique em **Iniciar / reconectar** no CRM. O gateway HTTPS usa o processo CRM existente. O servidor deve ficar ligado, com internet e CRM iniciado; a tarefa HTTPS sozinha não inicia o CRM após um reboot.

O certificado só será emitido se DNS e acesso público 80/443 estiverem corretos. A opção **3** grava `DIAGNOSTICO-IPHONE.txt`, que pode ser compartilhado: não contém credenciais. O log técnico do gateway fica em `data/external/caddy.log`; revisar localmente com TI, pois pode conter IPs/URLs de operação.

## 3. Validar fora da empresa e instalar

1. No iPhone, desligue o Wi-Fi e abra **https://crm.saisblue.com.br** no Safari. Deve mostrar login sem alerta de certificado.
2. Entre com a conta da atendente e confira que só aparecem as próprias oportunidades. O administrador mantém a visão completa.
3. Safari → **Compartilhar → Adicionar à Tela de Início → Adicionar**. Abra pelo novo ícone **Sais Blue CRM**. Requer iOS 16.4 ou superior.
4. Faça login no app instalado. Abra **Avisos → Ativar notificações do aparelho** e permita quando o iPhone solicitar.
5. Toque em **Testar em 10 segundos**, bloqueie o telefone e confirme o aviso. Em Ajustes → Notificações → Sais Blue CRM, confira permissão de tela bloqueada e sons. Modos Foco, silencioso e preferências do iOS podem silenciar o aviso.
6. Com um novo lead de anúncio, conclua perfil e cidade/UF. Confirme o aviso na conta atribuída e toque para abrir o card. Todo Lojista e Revenda de RS/SC → Chai; demais Revendas e todo Consumidor Final → Grasi.

## O que é preservado

Acesso interno continua em **http://192.168.0.219:3000**, com contas existentes. O app do WhatsApp Business no celular e o callback Meta/ngrok atual não são alterados. O app instalado precisa de conexão para abrir o CRM; dados pessoais e respostas das APIs não são gravados em cache offline.

As notificações exibem somente “Novo lead no CRM” e texto genérico na tela bloqueada. A equipe recebe apenas oportunidades atualmente atribuídas à sua conta. Transferências, exclusões, inativação e avisos já lidos são conferidos antes do envio; o card é conferido novamente ao abrir. Assinantes novos não recebem uma enxurrada de avisos antigos. Sair da conta desativa a inscrição daquele aparelho. Avisos aceitos pelo provedor ainda dependem de conectividade e das escolhas do iOS para a entrega.

As atualizações preservam `data`, a chave `webpush-private.pem` e o gateway HTTPS. Inclua a chave e `data/external` no backup privado da empresa; nunca envie esses arquivos ao GitHub. Não apague nem regenere a chave: isso invalidaria as inscrições dos aparelhos.
