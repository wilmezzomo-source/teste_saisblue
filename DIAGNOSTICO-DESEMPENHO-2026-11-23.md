# Diagnóstico de desempenho — 23/11/2026

A versão analisada é 2026.11.19.1, commit publicado beffa41. Esta análise não altera o aplicativo, o servidor da empresa, a configuração Meta ou contatos reais. Os ensaios usam uma base descartável de dados fictícios e a interface atual em Chromium local.

## O que foi confirmado no código

1. `/api/contacts` devolve todos os contatos acessíveis, todas as mensagens de cada contato e até 30 eventos de auditoria por contato. A ficha detalhada usa o mesmo conjunto já carregado. Não há paginação nessa lista.
2. A tela chama `load()` a cada cinco segundos, quando não há um campo em foco. Isso baixa de novo a base acessível e reconstrói o conteúdo, mesmo sem mudanças. Os filtros são aplicados depois de carregar tudo. Não há proteção explícita para evitar sobreposição de recargas demoradas.
3. O funil gera todos os cards e suas caixinhas de acompanhamento de uma vez. Trocar um filtro também reconstrói o conjunto visível. Histórico e auditoria ocupam transferência e memória mesmo quando a ficha não está aberta.
4. A listagem executa consultas adicionais por contato para mensagens, auditoria, situação do robô e acompanhamento. O custo cresce com a quantidade de contatos e conversas.
5. O banco já usa SQLite em modo WAL e tem índices em mensagens e auditoria. Faltam índices adequados à listagem de contatos por responsável/atualização e à consulta de telefone normalizado. O plano observado foi varredura de contatos e ordenação temporária.
6. A autenticação chama `restrict_administration()` inclusive em leituras e executa dois UPDATEs por chamada à API. Mesmo sem alteração efetiva, essas instruções exigem transação de escrita e podem disputar o único escritor do SQLite. A regra do administrador original deve continuar sendo verificada, por leitura, após a otimização.
7. O trabalhador do WhatsApp verifica a fila a cada segundo, sob `BEGIN IMMEDIATE`, e inclui consultas de manutenção e qualificação. Os lembretes internos percorrem os acompanhamentos a cada minuto durante o expediente. Esse trabalho deve ser medido e limitado às tarefas necessárias, preservando janela de 24h, distribuição e pedidos de não contato.

## Medições locais

Cada contato fictício tem 20 mensagens e 10 eventos de auditoria. Um quarto tem acompanhamento e metade usa a situação humana. Os tempos de API são medianas de três consultas após aquecimento, com cliente Flask local, incluindo geração da resposta JSON. A contagem SQL foi medida em consulta separada para não contaminar a mediana. As respostas abaixo são antes de eventual compressão de rede.

| Contatos | Mensagens | Resposta da lista | API local | SELECTs por recarga | Reconstrução + layout | Elementos na tela |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 2,000 | 1.42 MB | 43.3 ms | 669 | 52 ms | 3,299 |
| 1,000 | 20,000 | 14.20 MB | 446.3 ms | 6,654 | 445 ms | 31,019 |
| 5,000 | 100,000 | 71.03 MB | 2418.9 ms | 33,254 | 2246 ms | 154,219 |

O ensaio da interface usa o HTML, CSS e JavaScript atuais, APIs locais fictícias, desktop de 1440×1000, sem os temporizadores de atualização. Mede três reconstruções e espera dois quadros para layout. Atrasos de internet e o tempo de resposta do servidor não estão incluídos nesse tempo de interface. Não houve erro JavaScript.

Os tempos não representam o servidor Windows ou os celulares da empresa e não devem ser somados como um tempo exato de abertura. Demonstram o crescimento do trabalho: com 5.000 contatos, uma recarga transporta cerca de 71 MB sem compressão, faz 33.254 SELECTs e reconstrói mais de 154 mil elementos, inclusive quando os registros não mudaram.

## Atualização recomendada, por prioridade

### 1. Lista leve e histórico sob demanda

Criar uma consulta de resumos de oportunidades. Cada card recebe apenas os campos necessários, contagem de conversas, prévia da última mensagem e dados do próximo retorno. Mensagens completas e auditoria passam a ser carregadas ao abrir a ficha, com paginação também do histórico. As mensagens permanecem armazenadas.

### 2. Limitar o trabalho visível

Carregar um lote pequeno por coluna do funil e continuar conforme a rolagem, ou renderizar apenas a parte visível. Aplicar busca e filtros de perfil, responsável e data no servidor, com paginação estável. Contadores, valores e relatórios devem usar agregações da base autorizada completa, nunca apenas o lote exibido. O mapa também precisa de consulta própria de resumos, sem históricos.

### 3. Atualização incremental

Trazer só alterações desde a última atualização e alterar apenas os cards afetados. Evitar pedidos sobrepostos e recargas em aba oculta; conciliar o estado ao retornar. Considerar alterações em contatos, mensagens, acompanhamentos, transferências e exclusões. Uma mudança de responsável precisa remover imediatamente o card do acesso anterior. O vencimento de um lembrete precisa aparecer mesmo sem mensagem nova.

### 4. Banco e tarefas em segundo plano

Eliminar as consultas repetidas por contato, buscar os dados da página em conjunto e acrescentar índices medidos com planos de consulta. Remover gravações desnecessárias de rotas de leitura e encurtar transações de escrita. Consultar tarefas pelo vencimento, em lotes, evitando varrer o histórico inteiro a cada ciclo. Não manter transações abertas durante chamadas de rede. Preservar permissões, prevenção de duplicidade, opt-out, janela de 24h e integridade dos acompanhamentos.

### 5. Validar escala e dimensionar infraestrutura

Medir CPU, RAM disponível, disco/SSD, uso de outros programas e velocidade de upload no servidor Windows. Comparar interno e externo. Esses dados ainda não foram coletados; não há evidência para atribuir a lentidão a falta de RAM, disco ou ao provedor. Testar a nova versão com bases crescentes, histórico extenso e pelo menos três sessões simultâneas, junto com o trabalhador de mensagens.

SQLite pode continuar na primeira etapa: o modo WAL já está habilitado. A necessidade de migrar para PostgreSQL ou trocar o servidor deve ser decidida com medições de concorrência e carga após reduzir o trabalho desnecessário. Uma migração de banco, sozinha, mantém o custo de baixar históricos inteiros e reconstruir milhares de cards.

## Critérios para validar a melhoria

- Medir mediana e percentil 95 de abertura, busca, troca de filtro, arrastar card, marcar retorno e abrir ficha; registrar o cenário, dispositivo e quantidade de sessões.
- O lote de cards e seu volume de dados devem ter tamanho limitado, independente do total de histórico armazenado.
- O número de consultas da lista deve ser limitado por página, em vez de crescer com cada card.
- Uma atualização sem mudanças deve ter resposta pequena e preservar os elementos já desenhados.
- Confirmar que totais e filtros abrangem toda a base autorizada, e que atendentes não veem dados ou contadores de outras pessoas.
- Confirmar que anexar novas mensagens, transferir, excluir/restaurar e alterar um lembrete são refletidos sem perder rascunhos ou criar mensagens WhatsApp duplicadas.

Código consultado: server.py (database, protect, contacts e start_automation_worker); public/app.js (load, render e temporizador); followups.py (snapshot e reminders); qualification.py (process_outbox).
