# Validação da retomada local — 2026.11.16.1

## Comportamento

O servidor revisa pendências ao iniciar o assistente. Não depende de acesso externo à tela do CRM. A revisão seleciona somente oportunidades já identificadas por anúncio, sem responsável, em Novo contato, sem nenhuma resposta registrada e dentro de 24 horas da última mensagem recebida. A fila existente mantém seu processamento normal.

Uma resposta anterior aceita, enviada, entregue ou lida exclui o lead dessa retomada, mesmo que haja uma nova mensagem aguardando. O código preserva atendimento assumido, intervenção da equipe, pedido de interrupção, card excluído, cadastro manual, conversa orgânica, envio em processamento e envio sem confirmação. Rejeição conhecida pode receber uma tentativa por mensagem de entrada; outro clique ou reinício não repete uma tentativa já preparada.

O histórico é aproveitado antes de responder, inclusive perfil, cidade, estado e marca própria enviados em mensagens separadas com vários minutos entre elas. A UF por extenso que confirma a UF já inferida não troca o município: Cidade Ocidental, seguida de Goiás, permanece Cidade Ocidental/GO. A janela usa o horário original da mensagem, sem renovação pelo reinício.

Em Integrações, o administrador pode solicitar nova revisão e atualizar o diagnóstico. Contagens de fila, aceite da Meta, envio, entrega/leitura, falha e resultado incerto são distintas. Os endpoints exigem autenticação de administrador; a solicitação de retomada exige CSRF. Atendentes não recebem o diagnóstico global.

## Verificação

A [validação nativa do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43873679914) passou com 162 testes, sem falhas ou erros, incluindo o aplicativo real e o controle de início automático.

A [validação do canal publicado](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43874494830) também passou com 162 testes. O executável entregue baixou e instalou a versão 2026.11.16.1, confirmou a nova versão em execução e preservou banco e configuração em uma instalação Windows isolada.

A suíte local passou: 162 testes descobertos, com dois exclusivos do Windows ignorados no Linux. Os 15 cenários de retomada cobrem início real do trabalhador, fila existente, idempotência em clique/reinício, falha conhecida, envio incerto/em andamento, opt-out, intervenção humana, janela expirada, histórico em partes, PL/WL, cadastro manual, anúncios e controle de acesso.

O Chromium passou na interface final. Verificou a revisão pelo botão do administrador, o aceite da própria resposta de retomada e ausência de mensagens duplicadas. Os testes de edição, perfil, permissões, mapa, filtros, notificações, exclusão/restauração e visualização móvel continuaram passando. O service worker e a sintaxe JavaScript passaram.

O pacote imutável é o commit `c465660f4ca3b55402036081d30e3807127c9c03`, com SHA-256 `78aba2d1f4d771204d463df08b3b29c906c6234d1eaf4d37f705e41beea83051` e 3.723.858 bytes. Os módulos e o executável foram comparados aos arquivos locais. O pacote não inclui banco, `.env`, chaves privadas ou arquivos de execução.

## Aplicação na empresa

No servidor: **Sais Blue CRM → Atualizar e abrir CRM**. Depois recarregue o navegador e consulte **Integrações → Retomar atendimentos pendentes**. A revisão ocorre localmente, sem acesso remoto pelo chat de desenvolvimento. Os testes usam dados fictícios e transporte Meta simulado; não comprovam envios ou entrega aos contatos reais da empresa.

O conector não importa respostas enviadas apenas pelo aplicativo do celular nem consulta todo o histórico do WhatsApp. A elegibilidade considera o que está registrado no CRM. As mensagens que a Meta nunca entregou ao servidor não podem ser recuperadas por esse exame do banco. Fora de 24 horas, a versão não envia mensagens pela API.
