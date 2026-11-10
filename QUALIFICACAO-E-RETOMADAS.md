# Atendimento de anúncios — 2026.11.10.1

No servidor, use Sais Blue CRM → **Atualizar e abrir CRM**. O roteiro continua com a ativação e as contas de Chai/Grasi já salvas em Integrações. Não há novo token nem modelo para configurar.

- O WhatsApp não oferece ATENDENTE. O assistente acumula perfil, cidade e UF em mensagens separadas e continua pedindo apenas dados pendentes, sem limite de duas respostas.
- A cidade precisa existir no catálogo. Quando há uma única correspondência, a UF é preenchida automaticamente. Municípios homônimos exigem a UF; uma UF explicitamente incompatível nunca é substituída silenciosamente. Cidade Ocidental, Cidade Gaúcha e nomes terminados em estado, como Santa Maria do Pará, são preservados. Mensagens intercaladas não apagam os dados reconhecidos.
- Todo Lojista → Chai. Revenda de RS/SC → Chai. Revenda dos demais estados e todo Consumidor Final → Grasi. Na primeira execução, aplica a regra aos lojistas de anúncios em aberto, inclusive já qualificados. Preserva coluna, histórico e valores. Não reverte transferências manuais posteriores em cada execução, nem altera cadastros manuais ou vendas encerradas.
- Qualificar, atribuir e assumir não mudam a coluna. Um novo lead permanece em **Novo contato**. O time pode mudar a etapa explicitamente no formulário.

## Retomadas sem resposta

A primeira resposta continua imediata. Depois, há no máximo **quatro retomadas**, contadas da última mensagem do cliente: **20 minutos, 3 horas, 8 horas e 23h50**. Os textos variam: uma pergunta curta, uma lembrança de que o atendimento está salvo, um convite para enviar o dado pendente e uma despedida aberta para retomar quando quiser. Não repete a apresentação nem o questionário inteiro.

Essa é uma cadência inicial mais espaçada para avaliar o retorno da operação; não há promessa de um intervalo universal com maior conversão. A margem antes de 24h evita depender de modelos da Meta.

Cada resposta cancela as retomadas da pergunta anterior e reinicia a sequência apenas para os campos faltantes. Ao concluir o cadastro, os lembretes cessam. Na ficha aparece o próximo lembrete, a última tentativa ou o encerramento da janela. Uma resposta nova, mesmo em outro dia, pode retomar uma qualificação ainda pendente.

Os prazos ficam no banco e sobrevivem a reinícios. Se o servidor ficar desligado, não envia uma rajada para compensar os intervalos perdidos: mantém no mínimo uma hora entre retomadas após um atraso. Se já passou o horário da última tentativa mas ainda está dentro de 24h, envia somente a última. Se a janela encerrou antes de enviar, registra a situação e aguarda o cliente. **Não cria modelos nem envia mensagens fora de 24h.**

Cadastros manuais, conversas orgânicas fora do CRM, cards excluídos, qualificação concluída, intervenção da equipe pelo CRM, roteiro desativado e pedidos para parar não recebem esta sequência. Falhas de credenciais, entrega ou envio sem confirmação continuam visíveis e exigem revisão da equipe; não repete uma requisição de envio ambígua.

Qualificações antigas que pararam especificamente pelo limite de duas respostas, sem responsável e ainda em Novo contato, podem voltar ao roteiro. Usa os dados existentes; atendimentos assumidos manualmente e pedidos para parar permanecem pausados.

## Validação no número oficial

Abra um anúncio real, informe o perfil e envie cidade e UF separadamente, intercalando uma mensagem. Confira localização, perfil, responsável e coluna. Pare de responder e confira o próximo lembrete na ficha; uma resposta antes dele deve cancelar esse envio. O servidor, o CRM e o conector Meta precisam permanecer funcionando.

Os testes automatizados usam transporte Meta simulado e relógio controlado para os quatro horários e o limite de 24h. A validação no número real ocorre após atualizar o servidor da empresa.


## Contexto e pausas

“Tenho interesse em revender” já identifica Revenda. “Tenho interesse” seguido de “3” identifica Consumidor Final; uma mensagem de continuação não repete a pergunta feita há menos de dois minutos. Partes de uma cidade enviadas em sequência podem ser combinadas. A apresentação ocorre uma vez por conversa.

Ao atualizar, conversas pendentes com localização suficiente no histórico são corrigidas e encaminhadas, sem enviar uma nova mensagem de WhatsApp. Retomadas antigas já esgotadas não são reiniciadas. O horário e o total já enviados são preservados ao migrar a cadência.

Uma pausa por falha técnica pode retomar quando chega uma nova resposta do cliente, dentro da janela de 24h e sem intervenção manual. Isso não reenvia uma requisição ambígua: a nova mensagem inicia uma nova pergunta. Pausas por atendimento da equipe ou pedido para parar são preservadas. A ficha mostra o motivo da pausa e a situação do último envio. A imagem do WhatsApp, sozinha, não revela qual falha ocorreu no servidor da empresa.
