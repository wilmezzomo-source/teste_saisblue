# Sino, chamadas e atendimentos — 2026.11.19.1

Cada card mostra um **sino com a próxima chamada**. A equipe pode trabalhar direto no funil ou abrir **Retornos** para consultar as pessoas que precisa chamar.

## Marcar o atendimento e calcular a próxima chamada

No card, marque a caixinha do atendimento que realizou hoje: D0, D1, D3, D7 e D14 para Lojista; D0, D2, D5 e D10 para Revenda; D0, D1, D3 e D7 para Consumidor Final. Depois dessas etapas, há uma caixinha destacada de **Último retorno**: D30, D45 ou D15, respectivamente.

Não é necessário preencher outro formulário ou registrar etapas anteriores para começar. Marcar **D3** registra o atendimento de hoje e calcula **D7 quatro dias depois**. Para Revenda, marcar D2 calcula D5 três dias depois. Se a data cair no fim de semana, o lembrete fica para o próximo dia útil.

As etapas anteriores sem registro ficam esmaecidas, sem serem marcadas como realizadas. O histórico efetivamente registrado é preservado. Uma tentativa feita com atraso usa a data real do atendimento para calcular o próximo intervalo; não coloca a nova chamada em uma data que já passou.

Se precisar de uma data específica, clique no **sino**, escolha o dia e use **Agendar chamada**. Os atalhos Hoje e Amanhã preenchem a data. Uma data combinada substitui a sequência enquanto estiver em vigor. Ao registrar uma nova etapa realizada, a sequência continua a partir desse atendimento.

## Hoje e atrasados

- **Amarelo — Chamar hoje:** a chamada é para hoje.
- **Vermelho — ATRASADO:** mostra o vencimento e quantos dias passaram.
- **Azul — Próxima chamada:** apresenta a etapa e a data futura.
- **Verde — Cliente respondeu:** a conversa precisa orientar a próxima ação.
- **Roxo — Avaliar resultado ou revisão interna:** depende de decisão da equipe; não dispara mensagem comercial.
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

## Último retorno e decisão manual

| Perfil | Ao marcar | Próxima chamada |
| --- | --- | --- |
| Lojista | D14 | D30 |
| Revenda | D10 | D45 |
| Consumidor Final | D7 | D15 |

Os números são marcos da mesma tentativa. Os intervalos são, respectivamente, 16, 35 e 8 dias a partir da data real da chamada registrada. Exemplo: marcar D14 em 19/11 agenda D30 em 05/12; por cair no sábado, o lembrete aparece em 07/12. Datas combinadas manualmente e revisões personalizadas já salvas são preservadas.

O último retorno entra na agenda ativa e mostra o sino azul; no dia passa a amarelo e, se não realizado, fica vermelho com atraso. Ele não é somente uma revisão escondida. Marcar D30, D45 ou D15 registra que o retorno foi feito e coloca o card na fila **Retornos → Outras filas → Avaliar resultado**. A oportunidade fica na etapa atual. Se não houver compra, a responsável abre a ficha, escolhe **Perdido** e salva. Se comprar, escolhe **Ganho**. O CRM não decide isso sozinho para atendimentos humanos.

## Atendimento virtual sem resposta por 24 horas

Leads de anúncio que receberam uma pergunta do assistente, continuam sem resposta por 24 horas desde a última mensagem da cliente e não foram assumidos ou trabalhados pela equipe passam diretamente para **Perdido**, com **Sem Resposta** nas Observações. A coluna automática Qualificação pendente deixa de ser usada. Os sem responsável continuam visíveis apenas ao administrador.

O prazo considera a última mensagem recebida, não a idade do cadastro. Uma nova resposta renova a janela. Perguntas nunca enviadas, falhas de entrega, envios sem confirmação, atendimentos humanos, contatos manuais e oportunidades em outras etapas não são encerrados por essa regra. Se o servidor voltar depois da janela, o encerramento não dispara mensagens atrasadas. As perguntas, textos, intervalos e regras de distribuição do WhatsApp permanecem como estavam; somente a regra de encerramento muda.

## Opções adicionais

Na ficha, **Mais opções de acompanhamento** mantém data combinada, próximo passo de negociação, pausa, encerramento, não contato, última compra e ciclo de recompra. Negociação ativa não encerra só pela idade. Para recomeçar uma sequência, use **Reiniciar sequência hoje**; a data da última conversa não é inventada.

As faixas de recompra padrão de 30 dias continuam: 31–45 atenção, 46–60 risco, 61–90 inativo e acima de 90 dormente. O ciclo pode ser ajustado conforme reposição ou coleção. A agenda não inventa datas de compras anteriores.

Uma nova resposta recebida pelo CRM suspende a sequência de lembretes até a equipe definir o próximo passo. Pedidos para interromper contato continuam bloqueando novas abordagens. Os avisos internos respeitam dias úteis, das 9h às 18h de Brasília, sem calendário de feriados; a consulta da fila de hoje fica disponível durante o dia todo.

## Aplicar

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM** e recarregue o navegador. O banco, as datas e os atendimentos já registrados são preservados. O acesso externo e os convites continuam usando **http://200.225.129.156:3001**, com a porta interna preservada. O WhatsApp não recebe mensagens por estas ações de agenda. Notificações do aparelho continuam dependentes da configuração HTTPS existente.
