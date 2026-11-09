# Validação da qualificação — 2026.11.09.6

Pacote fixado no canal Windows: commit `69ac1bf1d399b9a9cefdaf472a08f2dfe0b9006f`, SHA-256 `b43ba1ce40efdb9cb3950a1022ac315d7c02c1d475e2aea9f6de4ce021b5753d`. ZIP conferido contra os arquivos locais; sem `.env`, banco ou chave privada.

Testes concluídos com dados fictícios e transporte Meta simulado:

- Qualificação: 27 testes. Incluem mais de duas respostas, ausência da opção ATENDENTE, cidade/UF em mensagens separadas ou intercaladas, correção de UF incorreta e dados preservados após reinício.
- Distribuição: todos os estados brasileiros, para cada um dos três perfis. Todo Lojista e Revenda de RS/SC seguem para Chai; demais Revendas e Consumidor Final para Grasi.
- Relógio simulado: intervalos de 5/10/30/60 minutos, última tentativa em 23h50, cancelamento ao responder, reinício, workers concorrentes, nenhuma rajada após indisponibilidade e bloqueio fora de 24h. Não cria nem envia template.
- Migração: aplica a regra aos lojistas de anúncio em aberto sem mudar a coluna; preserva cadastros manuais, outros perfis, vendas encerradas e transferências posteriores. Recupera conversas interrompidas especificamente pelo antigo limite de respostas, usando a forma como a versão antiga armazenava esse limite.
- Navegador Chromium: suíte completa de interface passou, incluindo acesso restrito, tags, filtros, WhatsApp, mapa, edição, exclusão/restauração, avisos e versão exibida. Service worker passou nos testes de privacidade e links.

A [validação final no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/42691846884/job/129413306790) passou: suíte Python de 95 testes e atualização nativa usando o executável e o pacote publicados. O service worker também passou. Os 27 testes de qualificação foram repetidos localmente após a correção da recuperação de conversas antigas.

A validação no número oficial depende de aplicar a atualização no servidor da empresa. Esta sessão não tem acesso a esse Windows nem às credenciais Meta reais; nenhum teste aqui enviou mensagens a clientes reais.
