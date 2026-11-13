# Atendimento com contexto, marca própria e Sem Resposta — 2026.11.13.1

## Conversa sem serviço de IA pago

O atendimento usa reconhecimento local de intenções e o histórico da conversa. Não exige chave, créditos, download de modelo ou API de IA. O GPT foi usado para desenvolver o código; não é executado no WhatsApp nem no servidor do CRM.

O roteiro pede apenas os dados faltantes, reconhece respostas em frases e partes enviadas separadamente e usa confirmações curtas. Exemplos: “para meu uso” identifica Consumidor Final; “quero começar a revender” identifica Revenda. Saudações e dúvidas comuns recebem uma resposta contextual. O sistema não inventa preços, estoque, condições comerciais ou prazos; essas orientações ficam para a consultora. Pedidos para interromper mensagens são respeitados.

Apenas leads de anúncios são admitidos automaticamente. Conversas orgânicas continuam fora do CRM; oportunidades manuais permanecem com atendimento humano. A ficha continua editável sem cidade/UF.

## White Label / Private Label / PL / WL

Esses interesses recebem o perfil **Marca própria (PL/WL)** e são encaminhados para o administrador original, Willian. A identificação usa o usuário original do CRM, não uma busca pelo nome da pessoa. O perfil aparece no filtro, nos cards e nos indicadores.

Após identificar a localização, o assistente pergunta a marca e o volume aproximado de peças por mês. Se esses dados já estiverem na conversa, aproveita-os. Se a cliente responder apenas uma parte, pergunta só a outra. As respostas ficam nas **Observações**, preservando o texto escrito pela equipe. Volumes informados em outra periodicidade são registrados como foram ditos, sem inventar uma conversão mensal.

Marca e volume são opcionais. Se a cliente não souber, o roteiro segue. Se ela não responder, encaminha com os dados disponíveis 15 minutos após a pergunta ter sido enviada. Essa espera não gera uma sequência extra de cobranças. O encaminhamento interno pode ocorrer após indisponibilidade do servidor, mas não há envio de WhatsApp fora das 24 horas. Intervenção da equipe ou pedido para parar cancela a espera automática.

As outras regras permanecem: todo Lojista → Chai; Revenda de RS/SC → Chai; demais Revendas e todo Consumidor Final → Grasi. O nome da responsável não é informado na confirmação ao cliente:

> Seu atendimento foi registrado. Em breve, uma consultora entrará em contato com você por aqui.

## Perdido — Sem Resposta

A janela considera a última mensagem recebida da cliente. Mantém as quatro retomadas em 20 minutos, 3 horas, 8 horas e 23h50. Apenas depois de encerrar as 24 horas, sem nova resposta e com as quatro retomadas aceitas/enviadas sem falha conhecida, move o lead para **Perdido** e acrescenta **Sem Resposta** nas Observações, sem apagar o conteúdo anterior.

Só fecha leads de anúncio ainda em Novo contato, sem responsável e com qualificação pendente. Não fecha por esse motivo atendimentos assumidos, oportunidades manuais, etapas alteradas pela equipe, pedidos de interrupção, envios com falha/incertos ou sequências incompletas após queda do servidor. Uma confirmação de falha de entrega recebida posteriormente desfaz esse encerramento automático e deixa o caso para revisão humana.

Uma nova resposta pode reabrir em Novo contato um lead fechado automaticamente, retirando apenas o marcador acrescentado pelo sistema. Se a equipe tiver alterado o card após o encerramento, sua decisão é preservada. A reabertura não modifica perdas manuais e não envia mensagens fora da janela permitida.

## Atualizar

No servidor: **Sais Blue CRM → Atualizar e abrir CRM**. Depois, recarregue o CRM nos navegadores da equipe. Não é necessário configurar nova API de IA. O banco, os acessos e a conexão Meta existente são preservados pelo atualizador.
