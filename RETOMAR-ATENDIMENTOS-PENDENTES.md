# Retomar atendimentos pendentes — 2026.11.16.1

O servidor consegue atender pelo WhatsApp mesmo quando a tela do CRM só abre dentro da empresa. Precisa de internet, credenciais válidas da Meta, primeiro atendimento ativado e mensagens registradas. O acesso externo à tela e a confirmação do início automático do Windows são verificações separadas.

## Aplicar agora

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM**. Esta versão revisa as pendências ao iniciar o assistente. A retomada funciona na própria instalação; o chat de desenvolvimento não tem acesso remoto aos contatos da empresa.

Depois recarregue o navegador e abra **Integrações → Retomar atendimentos pendentes**. O administrador pode clicar em **Retomar pendentes** e **Atualizar diagnóstico**. O painel separa respostas preparadas, na fila, aceitas pela Meta, enviadas, entregues/lidas, com falha e sem confirmação. Preparar uma resposta ou receber aceite da Meta não comprova entrega no telefone.

## Quais contatos podem retomar

Apenas oportunidades de anúncios já registradas, sem responsável, em Novo contato, que ainda não receberam nenhuma resposta registrada no CRM e dentro das 24 horas da última mensagem da cliente. A retomada aproveita perfil, cidade/UF e dados de marca própria enviados em partes, inclusive com vários minutos entre mensagens. Não zera a janela de atendimento ao reiniciar.

Uma falha técnica com rejeição conhecida pode receber uma tentativa de retomada por mensagem de entrada. Outro clique ou reinício não repete essa tentativa. Mensagens já aceitas/enviadas, em processamento ou sem confirmação não são reenviadas. A fila existente continua sendo processada pelo trabalhador normal do CRM.

Atendimentos assumidos, alterações da equipe, pedidos de interrupção, cards excluídos, etapas alteradas, oportunidades manuais e conversas orgânicas são preservados. Não busca conversas diretamente no celular nem recupera eventos que a Meta nunca entregou ao servidor. O CRM continua sem importar os envios feitos pelo aplicativo do celular; é necessário considerar atendimentos feitos por esse canal ao revisar casos na equipe.

Mensagens fora de 24 horas não recebem envio pela API nesta versão. Para esses casos, use **Chamar no WhatsApp** e continue pelo WhatsApp Business. Credenciais expiradas, internet indisponível ou entrega bloqueada pela Meta continuam exigindo correção da conexão.

O aviso de início automático não confirmado deve ser resolvido em **Iniciar / reconectar**, autorizando o pedido do Windows. Enquanto isso, a mensagem de CRM iniciado confirma apenas a aplicação nessa sessão; o diagnóstico de envio deve ser conferido separadamente.
