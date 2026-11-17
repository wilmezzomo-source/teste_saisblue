# Retornos e lembretes internos — 2026.11.17.1

No menu **Retornos**, a equipe encontra contatos para hoje, atrasados, agendados, revisões, clientes que responderam, qualificação pendente, clientes que já compraram e contatos sem agenda. Perfil, responsável e período podem ser combinados. Atendentes acessam apenas suas próprias oportunidades; o administrador acompanha toda a equipe.

## Registrar o acompanhamento

1. Abra o card e localize **Acompanhamento e lembretes**.
2. Informe **Data da última conversa**, correspondente à última conversa com resposta do cliente.
3. Use **Identificado · aguardando resposta** para iniciar a sequência do perfil, ou escolha retorno combinado, conversa ativa/negociação, cliente que já comprou, pausa ou encerramento.
4. Clique em **Salvar acompanhamento**. O formulário sugere a sequência pelo perfil; para clientes na etapa Ganho, sugere recompra. Apenas informar a data pela API também inicia a sequência pertinente.
5. Ao realizar uma tentativa, marque a caixinha correspondente. A marcação salva automaticamente. A última tentativa fica separada da última conversa, e D0 permanece o início da tentativa.

Para iniciar outra tentativa a partir da mesma data, use **Nova tentativa a partir da última conversa**. Alterar a data da última conversa ao manter a situação de aguardando resposta também inicia uma nova sequência. As mudanças ficam no histórico; marcar uma tentativa não altera a etapa ou responsável do card.

| Situação | Sequência | Depois |
| --- | --- | --- |
| Identificação pendente | Primeiras 24 horas | Qualificação pendente; fora da fila ativa de retornos |
| Lojista | D0, D1, D3, D7, D14 | Pausa e revisão interna em D30 |
| Revenda | D0, D2, D5, D10 | Pausa e revisão padrão D45, ajustável conforme a janela D30–D60 |
| Consumidor Final | D0, D1, D3, D7 | Tentativa encerrada; não cria nova abordagem |
| Data combinada | Data informada pela consultora | Substitui a sequência anterior |
| Conversa ativa / negociação | Próximo passo e data obrigatórios | Não encerra pela idade do cadastro |
| Não receber contato | Interrupção dos lembretes comerciais | Sem nova data de abordagem |

Os intervalos usam dias corridos. Lembretes de sequência que caem no fim de semana são apresentados no próximo dia útil. Lembretes e revisões são gerados de segunda a sexta, das 9h às 18h, no horário de Brasília. Feriados não são descontados. Uma data expressamente combinada permanece como foi informada; os avisos respeitam o expediente. Uma tentativa realmente feita pode ser registrada antes das 9h no próprio dia, sem antecipar o aviso.

Não há acúmulo de tentativas para fazer em uma rajada: ao registrar uma etapa posterior, as etapas anteriores sem registro continuam identificadas como não realizadas. Prazos que caem na mesma data útil são cobertos por um único contato. No fim da sequência, o contato vai para revisão ou encerramento, mesmo que não tenham sido marcadas todas as tentativas. Uma revisão é uma tarefa interna para avaliar contexto, não uma mensagem automática.

Se uma nova resposta do cliente chegar ao CRM durante a sequência, os próximos lembretes ficam suspensos e o contato aparece em **Cliente respondeu**. A equipe registra a conversa e define uma data combinada ou o próximo passo. Conversas feitas somente pelo telefone, sem mensagem recebida pelo CRM, dependem desse registro manual. Um pedido recebido para interromper mensagens também bloqueia novos lembretes internos; a equipe deve manter o registro de não contato.

## Clientes que já compraram

Escolha **Cliente que já comprou**, preencha a última compra e o ciclo real em dias. O padrão é 30 dias: até 30 no ciclo; 31–45 atenção; 46–60 risco; 61–90 inativo; acima de 90 dormente. Para outro ciclo, os limites são proporcionais: 1, 1,5, 2 e 3 ciclos. Ajuste a referência conforme reposição ou coleção. A etapa Ganho não inventa uma data de compra: ela precisa ser informada.

## Filtro de datas

Ao lado de perfil e responsável, escolha **Data de**: entrada no CRM, última conversa, próximo retorno/revisão ou última compra. Preencha **De / Até**; os limites são inclusivos e usam o dia de Brasília. Os filtros valem juntos no funil, contatos, atendimento, retornos, mapa e indicadores. Um contato sem a data escolhida fica fora de um intervalo preenchido. **Limpar datas** remove apenas esse intervalo.

## Qualificação pendente e WhatsApp

A nova coluna separa visualmente leads de anúncio sem perfil ou localização após 24 horas sem resposta de identificação. Ela não reabre atendimentos assumidos, cadastros manuais ou perdas manuais. Também pode ser selecionada como etapa pela equipe. Contatos expirados ficam fora dos indicadores de oportunidades ativas e da fila de retornos de hoje.

A classificação automática dessa coluna é uma exibição interna: não reescreve o estado ou a etapa usados pelo assistente, não reinicia qualificação e não muda os envios existentes. Os arquivos `qualification.py`, `qualification_dialogue.py` e `qualification_location.py` permanecem iguais aos da versão 2026.11.16.3. Os ajustes adicionais de WhatsApp que estavam em preparação não integram esta atualização interna.

Esta agenda não envia WhatsApp. Os avisos aparecem em **Avisos**, com o mesmo controle de acesso e opção de som já existentes. O aviso é criado apenas para a responsável atual, ou para o administrador quando não há responsável. Avisos são deduplicados. Notificações no aparelho usam a configuração Web Push já existente e exigem HTTPS; a atualização não comprova entrega real no iPhone.

## Acesso externo informado

O acesso da equipe e os convites passam a usar **http://200.225.129.156:3001** na instalação HTTP atual. Login e alterações aceitam esse endereço exato, mantendo autenticação, CSRF e restrições por atendente. Outros endereços e portas não são liberados como origem externa. A porta interna atual do serviço permanece igual, preservando o redirecionamento que a empresa já utiliza.

Não são alterados roteador, callback, ngrok ou credenciais Meta. O endereço pode ser substituído por `CRM_ACCESS_URL` no `.env`. Uma instalação configurada com HTTPS não é rebaixada para HTTP. O endereço HTTP não permite instalar o app do iPhone nem receber notificações de tela bloqueada; esses recursos continuam dependentes do HTTPS existente em preparação.

A consulta ao IP externo a partir deste ambiente foi recusada pelo gateway com `403 Domain forbidden`, portanto a acessibilidade real pela internet não foi confirmada aqui. Os testes do endereço foram feitos no cliente HTTP isolado do CRM.

## Aplicar

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM** e depois recarregue o navegador. As datas antigas não são inventadas: a equipe preenche a última conversa ou compra para iniciar o acompanhamento. O servidor precisa permanecer ligado para gerar os avisos.
