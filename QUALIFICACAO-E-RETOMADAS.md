# Atendimento de anúncios — 2026.11.09.6

No servidor, use Sais Blue CRM → **Atualizar e abrir CRM**. O roteiro continua com a ativação e as contas de Chai/Grasi já salvas em Integrações. Não há novo token nem modelo para configurar.

- O WhatsApp não oferece ATENDENTE. O assistente acumula perfil, cidade e UF em mensagens separadas e continua pedindo apenas dados pendentes, sem limite de duas respostas.
- A cidade precisa existir no catálogo com a UF informada. A combinação errada não é presumida. Mensagens intercaladas não apagam a cidade ou o estado já reconhecidos.
- Todo Lojista → Chai. Revenda de RS/SC → Chai. Revenda dos demais estados e todo Consumidor Final → Grasi. Na primeira execução, aplica a regra aos lojistas de anúncios em aberto, inclusive já qualificados. Preserva coluna, histórico e valores. Não reverte transferências manuais posteriores em cada execução, nem altera cadastros manuais ou vendas encerradas.
- Qualificar, atribuir e assumir não mudam a coluna. Um novo lead permanece em **Novo contato**. O time pode mudar a etapa explicitamente no formulário.

## Retomadas sem resposta

Após a pergunta ser aceita pela Meta, o primeiro lembrete aguarda 5 minutos. Os seguintes aguardam 10, 30 e 60 minutos depois do envio anterior. Em operação contínua, isso corresponde a aproximadamente 5, 15, 45 e 105 minutos depois da pergunta. A última tentativa ocorre **23h50 depois da última mensagem recebida do cliente**, deixando uma margem antes do limite da API.

Cada resposta cancela as retomadas da pergunta anterior e reinicia a sequência apenas para os campos faltantes. Ao concluir o cadastro, os lembretes cessam. Na ficha aparece o próximo lembrete, a última tentativa ou o encerramento da janela. Uma resposta nova, mesmo em outro dia, pode retomar uma qualificação ainda pendente.

Os prazos ficam no banco e sobrevivem a reinícios. Se o servidor ficar desligado, não envia uma rajada para compensar os intervalos perdidos: usa o próximo intervalo a partir do envio efetivo. Se já passou o horário da última tentativa mas ainda está dentro de 24h, envia somente a última. Se a janela encerrou antes de enviar, registra a situação e aguarda o cliente. **Não cria modelos nem envia mensagens fora de 24h.**

Cadastros manuais, conversas orgânicas fora do CRM, cards excluídos, qualificação concluída, intervenção da equipe pelo CRM, roteiro desativado e pedidos para parar não recebem esta sequência. Falhas de credenciais, entrega ou envio sem confirmação continuam visíveis e exigem revisão da equipe; não repete uma requisição de envio ambígua.

Qualificações antigas que pararam especificamente pelo limite de duas respostas, sem responsável e ainda em Novo contato, podem voltar ao roteiro. Usa os dados existentes; atendimentos assumidos manualmente e pedidos para parar permanecem pausados.

## Validação no número oficial

Abra um anúncio real, informe o perfil e envie cidade e UF separadamente, intercalando uma mensagem. Confira localização, perfil, responsável e coluna. Pare de responder e confira o próximo lembrete na ficha; uma resposta antes dele deve cancelar esse envio. O servidor, o CRM e o conector Meta precisam permanecer funcionando.

Os testes automatizados usam transporte Meta simulado e relógio controlado para os cinco intervalos e o limite de 24h. A validação no número real ocorre após atualizar o servidor da empresa.
