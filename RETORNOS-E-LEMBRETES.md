# Sino, chamadas e atendimentos — 2026.11.17.2

Cada card mostra um **sino com a próxima chamada**. A equipe pode trabalhar direto no funil ou abrir **Retornos** para consultar as pessoas que precisa chamar.

## Marcar o atendimento e calcular a próxima chamada

No card, marque a caixinha do atendimento que realizou hoje: D0, D1, D3, D7 ou D14 para Lojista; D0, D2, D5 ou D10 para Revenda; D0, D1, D3 ou D7 para Consumidor Final.

Não é necessário preencher outro formulário ou registrar etapas anteriores para começar. Marcar **D3** registra o atendimento de hoje e calcula **D7 quatro dias depois**. Para Revenda, marcar D2 calcula D5 três dias depois. Se a data cair no fim de semana, o lembrete fica para o próximo dia útil.

As etapas anteriores sem registro ficam esmaecidas, sem serem marcadas como realizadas. O histórico efetivamente registrado é preservado. Uma tentativa feita com atraso usa a data real do atendimento para calcular o próximo intervalo; não coloca a nova chamada em uma data que já passou.

Se precisar de uma data específica, clique no **sino**, escolha o dia e use **Agendar chamada**. Os atalhos Hoje e Amanhã preenchem a data. Uma data combinada substitui a sequência enquanto estiver em vigor. Ao registrar uma nova etapa realizada, a sequência continua a partir desse atendimento.

## Hoje e atrasados

- **Amarelo — Chamar hoje:** a chamada é para hoje.
- **Vermelho — ATRASADO:** mostra o vencimento e quantos dias passaram.
- **Azul — Próxima chamada:** apresenta a etapa e a data futura.
- **Verde — Cliente respondeu:** a conversa precisa orientar a próxima ação.
- **Roxo — Revisão interna:** serve para avaliar o contexto; não dispara mensagem comercial.
- **Cinza — Agendar chamada:** ainda não existe uma data definida.

Uma etapa não realizada **continua atrasada**. Não é marcada automaticamente nem desaparece da fila por envelhecer. Ela sai desse estado quando a equipe registra o atendimento, combina outra data ou pausa/encerra o acompanhamento.

Em **Retornos**, os contadores Atrasados, Para hoje e Sem próxima chamada levam à fila correspondente. Os filtros de perfil e responsável continuam valendo. A fila é atualizada ao abrir o menu; os avisos e a atualização periódica continuam disponíveis.

## Filtro de data simples

Ao lado de perfil e responsável existe apenas **Próxima chamada**:

- Todas as datas;
- Chamar hoje;
- Atrasados;
- Amanhã;
- Próximos 7 dias;
- Sem agendamento;
- Escolher período.

Os campos De/Até aparecem somente ao escolher um período. Os limites incluem os dois dias, no horário de Brasília. O botão × limpa a data e mantém perfil e responsável. Os atalhos da agenda trocam a fila sem deixar um período anterior ocultando contatos indevidamente.

## Qualificação pendente — somente o administrador

A coluna é exclusiva do administrador e não é compartilhada ou distribuída entre atendentes. Ela reúne leads de anúncio **sem perfil, sem localização e sem responsável**, depois de **24 horas desde a primeira mensagem**, quando as tentativas do assistente virtual já se esgotaram.

Um lead que informou perfil ou localização não entra nessa classificação de ausência total de identificação. Os demais controles de acesso são preservados: cada atendente vê apenas suas próprias oportunidades. A coluna automática não é uma etapa para arrastar cards manualmente.

Essa classificação é da exibição interna. Não reescreve os registros de qualificação usados pelo assistente nem muda envios, responsáveis ou o atendimento do WhatsApp.

## Revisões e opções adicionais

Ao registrar a última etapa, Lojista passa à revisão interna de D30; Revenda tem revisão padrão D45, ajustável conforme o contexto de D30–D60; Consumidor Final encerra a tentativa. Os intervalos de revisão partem do atendimento realizado. Uma revisão não significa enviar mensagem automaticamente.

Na ficha, **Mais opções de acompanhamento** mantém data combinada, próximo passo de negociação, pausa, encerramento, não contato, última compra e ciclo de recompra. Negociação ativa não encerra só pela idade. Para recomeçar uma sequência, use **Reiniciar sequência hoje**; a data da última conversa não é inventada.

As faixas de recompra padrão de 30 dias continuam: 31–45 atenção, 46–60 risco, 61–90 inativo e acima de 90 dormente. O ciclo pode ser ajustado conforme reposição ou coleção. A agenda não inventa datas de compras anteriores.

Uma nova resposta recebida pelo CRM suspende a sequência de lembretes até a equipe definir o próximo passo. Pedidos para interromper contato continuam bloqueando novas abordagens. Os avisos internos respeitam dias úteis, das 9h às 18h de Brasília, sem calendário de feriados; a consulta da fila de hoje fica disponível durante o dia todo.

## Aplicar

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM** e recarregue o navegador. O banco, as datas e os atendimentos já registrados são preservados. O acesso externo e os convites continuam usando **http://200.225.129.156:3001**, com a porta interna preservada. O WhatsApp não recebe mensagens por estas ações de agenda. Notificações do aparelho continuam dependentes da configuração HTTPS existente.
