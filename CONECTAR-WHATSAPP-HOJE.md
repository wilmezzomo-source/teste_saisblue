# Conectar o número oficial — piloto HTTPS com ngrok

O número **Sais Blue – Willian, +55 54 3443-6405**, apareceu como **Inscrito** no app da Meta após o fluxo de conexão pelo aplicativo. O Phone Number ID observado é **321395016679053** e a referência da conta **1398958113869625**. O QR lido no aplicativo é a etapa de onboarding; ainda faltam credenciais, endpoint, assinatura e validação de mensagens.

Este pacote usa um túnel ngrok **somente para o webhook**. O usuário autorizou esse serviço para teste. Os eventos passam pela infraestrutura do ngrok; o CRM, sua página de login e suas APIs continuam na rede local. É um piloto: limites do plano do ngrok, conexão, janelas abertas e configuração da Meta afetam a disponibilidade. Não é uma instalação de produção permanente e não altera o DNS/site/e-mails.

## 1. Atualizar sem reinstalar

No Windows do servidor, pare o CRM com Ctrl+C. Extraia o ZIP novo em outra pasta. Nessa pasta nova, abra **ATUALIZAR-NO-WINDOWS.cmd** e selecione a pasta antiga onde o CRM já funciona. O atualizador agora usa a seleção de pasta do Windows e o Python da instalação antiga, sem depender de `py`. Ele cria backup e preserva `.env`, banco e usuários.

Após atualizar, todos os passos seguintes são na **pasta antiga**. A aplicação mostra **2026.11.06.3** após iniciar.

## 2. Preparar o ngrok no Windows

Crie a conta de teste gratuita em https://dashboard.ngrok.com/signup. No painel, escolha instalação **Windows**. Baixe e extraia o agente oficial, e copie **ngrok.exe** para a pasta antiga do CRM (a mesma de INICIAR-NO-WINDOWS.cmd). Abrir o exe sem argumentos mostra apenas a ajuda; isso não inicia o túnel.

No painel ngrok, localize **Your Authtoken**. Ele é diferente do token da Meta e será colado somente no terminal local. Nenhum plano pago ou domínio personalizado é necessário para esta implementação de teste. Não siga exemplos apontando para portas 80 ou 3000: o conector inicia o ngrok para **127.0.0.1:3002**.

## 3. Configurar as credenciais no servidor

Execute **CONFIGURAR-META-E-HTTPS.cmd**. Ele solicita, sem exibir durante a digitação:

1. **Token de acesso Meta** autorizado para **Sais Blue – Willian**, depois da inscrição do número. Se os escopos granulares ainda apontam apenas à conta de teste 2588658694895615, gere um token com acesso à conta oficial antes de usar.
2. **App Secret / Chave secreta** do app **Sais Blue CRM**. No painel Meta: **Configurações do app → Básico → Chave secreta → Mostrar**. Não é o ID do app nem o token da Meta.
3. **Authtoken ngrok**, obtido no painel ngrok.

Enter mantém um valor que já esteja configurado. O programa consulta a Meta para conferir o número oficial e a chave do app antes de salvar, gera o token de verificação do webhook e preserva o endereço LAN e o banco. Só faz consultas GET à Meta; não envia mensagens nem registra/migra o número. Os segredos ficam em `.env`, no servidor, e não entram no Git. Restrinja o acesso à pasta e não envie os valores no chat.

**Validação:** a configuração termina com “Credenciais conferidas pela Meta e salvas no servidor”. Se houver código de erro, pare nessa etapa e compartilhe somente a mensagem, sem tokens.

## 4. Iniciar o CRM e o túnel

1. Se o CRM ainda estiver aberto, pare-o com Ctrl+C para carregar a configuração nova.
2. Execute **INICIAR-NO-WINDOWS.cmd** e deixe essa janela aberta.
3. Execute **INICIAR-CONEXAO-HTTPS.cmd** em outra janela.

O conector confere a verificação local e um evento vazio assinado, abre um gateway restrito em 127.0.0.1:3002, inicia seu ngrok com o authtoken em variável de ambiente (não em argumentos) e desliga a inspeção de requisições do agente. Verifica o desafio público e exige que `/`, `/login` e `/api/contacts` respondam 404 no túnel.

**Validação:** aparece **URL PÚBLICA VALIDADA: https://.../webhooks/whatsapp**. A URL é obtida do seu agente; nenhum endereço ngrok foi inventado ou pré-configurado no pacote. Se falhar, mantenha a mensagem de erro para diagnóstico. Não considere um túnel ativo só porque a janela de ajuda do ngrok abriu.

A URL e o token de verificação são gravados em **META-CONFIGURACAO-LOCAL.txt**. Esse arquivo é para uso no servidor; não o envie aqui. O token de verificação é diferente dos dois tokens de acesso solicitados antes.

## 5. Preencher a Meta

No app **Sais Blue CRM → Etapa 2 → Configurar webhooks**:

1. Copie a **URL de callback** do arquivo local.
2. Copie o **token de verificação** para **Verificar token**.
3. Clique em **Verificar e salvar**.
4. Em **Registre seu número**, ative **Assinar webhooks** para **Sais Blue – Willian**.
5. Confirme a assinatura do campo `messages` se o painel solicitar.
6. Atenda os requisitos de publicação exibidos pela Meta. Se o painel ainda informar que o app não publicado só recebe eventos sintéticos, a integração de produção não está pronta. Não confunda a publicação do ambiente de desenvolvimento com a publicação do app Meta.

**Validação:** o painel aceita o callback e a assinatura da conta oficial fica ativada. Isso ainda não comprova a entrega de uma mensagem real.

## 6. Teste final com o número oficial

Um colega envia uma mensagem pelo WhatsApp para **+55 54 3443-6405**. Confirme que o WhatsApp Business continua recebendo no celular e que o contato/mensagem aparecem no CRM. Complete cidade/UF e responda pela ficha dentro da janela de 24h. O colega confirma a resposta no celular. Por último, valide a entrada pelo anúncio e a origem quando a Meta a disponibilizar.

A integração só está validada quando esse percurso funciona. A versão atual processa mensagens novas e respostas pelo CRM; não importa histórico antigo ou sincroniza automaticamente os envios feitos diretamente pelo aplicativo via eventos de eco. Mídias recebidas aparecem como indicação do tipo, sem download/reprodução. Templates fora da janela de 24h ainda não estão implementados.

## Operação do piloto

Mantenha **as duas janelas** abertas: CRM e conexão HTTPS. O conector encerra somente o agente ngrok que ele iniciou quando você fecha a conexão. Se a URL do ngrok mudar ao reiniciar, repita a verificação/atualização do callback na Meta. O túnel não substitui backup, monitoramento ou instalação persistente de produção. Para operação contínua, planeje domínio/HTTPS e início automático com TI/Telium, ou um serviço de túnel persistente adequado.

Testes automatizados validam assinaturas, preservação dos bytes, isolamento de rotas, validação de desafio, escolha da porta do agente e o percurso gateway → backend → cadastro de lead de anúncio com deduplicação. A conexão com sua conta ngrok, a instalação do agente e a entrega Meta real precisam ser confirmadas no Windows da empresa.
