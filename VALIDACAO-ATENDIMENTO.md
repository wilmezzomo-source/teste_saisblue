# Validação do atendimento — 2026.11.10.1

Pacote fixado no commit `bed72283b767d9dfa53be346e6405bf43efbc64c`, com SHA-256 `597ed81edca48b0947ed05bbde12cb2802c667c537b56b2722a5122d8819176a`. O ZIP foi comparado aos arquivos locais, incluindo o novo módulo de municípios e o executável Windows. Não inclui banco, `.env`, tokens ou chaves privadas.

Casos reproduzidos com dados fictícios:

- Revenda + “Cidade Ocidental Goiás” conclui em Cidade Ocidental/GO, encaminha para Grasi e mantém Novo contato. “Ocidental Goiás” é uma abreviação reconhecida pelo catálogo.
- “Tenho interesse” seguido de “3” não repete o menu; identifica Consumidor Final e segue para a cidade.
- “Tenho interesse em revender” já identifica Revenda. Respostas novas podem retomar uma pausa técnica, incluindo eventos distintos recebidos no mesmo segundo, sem reabrir atendimento manual ou pedidos para parar.
- Todos os nomes oficiais com uma única correspondência no catálogo brasileiro preenchem UF. Municípios homônimos, como Bom Jesus, continuam pedindo estado. UF explicitamente incompatível não é substituída silenciosamente.
- Partes de nomes em mensagens separadas, nomes iniciados em Cidade e nomes terminados em estado foram testados. São preservadas as respostas já reconhecidas e a ordem de chegada de mensagens no mesmo segundo.
- Relógio simulado confirma até quatro retomadas: 20 minutos, 3 horas, 8 horas e 23h50. Os textos são diferentes, curtos e sem reapresentação. Não envia modelos nem mensagens fora de 24h.
- A atualização não reinicia sequências já esgotadas. Informações suficientes no histórico corrigem qualificações pendentes sem enviar WhatsApp desnecessário. Uma escolha de perfil já recebida e ignorada pode avançar para a cidade, sem perguntar o perfil novamente.

A suíte completa local passou e o Chromium real validou a interface, versão, qualificação, acesso por responsável, mapa, filtros, edição, exclusão/restauração e avisos. Os testes específicos de qualificação foram repetidos após os ajustes de recuperação do histórico. O teste de privacidade do service worker passou.

A [validação Windows do código final](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/42822414040/job/129851001117) passou, incluindo os 108 testes Python e o aplicativo nativo de atualização. A [checagem do pacote final pelo atualizador](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/42823057352/job/129853177385) também passou, usando o executável entregue e o pacote fixado no canal. Os testes usam transporte Meta simulado. Não houve acesso ao servidor da empresa nem envio de teste a clientes reais; a aplicação operacional depende de atualizar no Windows e conferir o rodapé 2026.11.10.1.

A imagem do WhatsApp não permite determinar sozinha por que um atendimento parou. O CRM passa a mostrar o motivo de pausa e o estado/código do último envio, para distinguir falhas técnicas de atendimento assumido pela equipe.
