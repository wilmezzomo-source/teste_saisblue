# Desempenho e distribuição — 2026.11.23.1

O aplicativo passa a carregar resumos paginados. O histórico completo permanece no banco e é buscado quando a ficha é aberta.

## Uso da equipe

- O funil mostra até **30 cards por coluna**, com o total completo no cabeçalho. Use Anteriores e Próximos no rodapé da coluna para navegar. A busca procura na base inteira autorizada, inclusive fora da página atual.
- Contatos, Atendimento e Retornos também têm páginas de 30 registros. Filtros de perfil, responsável e próxima chamada continuam combináveis. Indicadores e relatórios usam a base autorizada completa.
- Abrir uma ficha carrega as 100 mensagens mais recentes. Use **Ver mensagens anteriores** para consultar o restante. **Ver atividades anteriores** continua a auditoria em páginas de 30 eventos. Carregar mensagens/atividades anteriores preserva o rascunho da Observação.
- O sino e os marcos D0/D1/D3 etc. continuam no card, com os mesmos prazos e alertas de atraso. Uma ficha ou aviso abre por ID, mesmo que o contato esteja em outra página.
- O mapa recebe totais por município. Os nomes são buscados ao abrir o pin, em páginas; a lista de pendências também é paginada. O filtro de estado do mapa continua preservando as pendências de localização da carteira.
- Cada atendente continua vendo somente os próprios cards. Transferência e exclusão revogam o acesso à ficha aberta. O administrador original mantém a visão global.

## Distribuição automática

**Chai:** todos os Lojistas; Revendas de RS, SC e PR.

**Grasi:** demais Revendas e todo Consumidor Final.

**Willian:** White Label / Private Label / PL / WL, com marca e volume opcionais nas Observações. As atribuições manuais não são redistribuídas por esta atualização. As perguntas e textos do assistente, a janela de 24 horas e o encerramento por Sem Resposta foram preservados.

## O que mudou no funcionamento

A nova consulta `/api/workspace` entrega resumos, páginas e agregações. Mensagens completas, observações e auditoria são acessadas pela ficha autorizada, com cursores estáveis para mensagens com o mesmo horário. A rota anterior foi mantida para compatibilidade; a interface atualizada usa a nova rota.

Um marcador privado de versão permite responder **304 sem corpo** quando nada mudou. O marcador muda por carteira: uma alteração de outra responsável não força recarga de uma atendente. Mudanças de propriedade invalidam as duas carteiras. O dia de Brasília também participa do marcador para atualizar vencimentos sem exigir uma mensagem nova.

Os resumos são persistidos e somente contatos alterados são recalculados. Contadores de mensagens são mantidos por alterações do histórico, sem recontar a conversa inteira em cada recarga. Uma atualização futura invalida o modelo derivado para aplicar novas regras, preservando os registros originais. Buscas e contagens respeitam as permissões no servidor.

No funil, cards idênticos são mantidos; somente os alterados são substituídos ou movidos. As recargas não se sobrepõem. Abas ocultas deixam de fazer consultas periódicas e conciliam o estado ao voltar. O navegador mantém o trabalho de edição durante atualizações de fundo; durante um salvamento, os campos da ficha aguardam sua conclusão.

Foram acrescentados índices para responsável, etapa, ordenação e mensagens. A autenticação de leitura verifica o administrador original sem executar UPDATEs a cada consulta. O trabalhador do WhatsApp usa uma sondagem de leitura quando está ocioso; verificações amplas de manutenção passam a ser feitas a cada minuto. Com o assistente desativado, temporizadores antigos não provocam bloqueios de escrita a cada segundo. Envios e temporizadores vencidos continuam acordando o trabalhador, sem aguardar o próximo ciclo de manutenção. Os lembretes internos consultam os resumos e vencimentos, em vez de reler todos os históricos a cada minuto.

## Medições locais com dados fictícios

Mesma base do diagnóstico: 5.000 contatos, 100.000 mensagens e 50.000 eventos de auditoria. Cada contato tem 20 mensagens. Estes números medem o ambiente de teste Linux/Chromium, sem a rede da empresa; não são medições do Windows ou do link externo real.

| Medida | Antes | Depois |
| --- | --- | --- |
| Dados da lista, sem compressão | 71,03 MB | 228.625 bytes, cerca de 229 KB |
| SELECTs por leitura da lista | 33.254 | 20 |
| Tempo mediano da API local | 2.418,9 ms | 28,3 ms com resumos preparados |
| Cards presentes no funil | 5.000 | 150, com acesso às demais páginas |
| Elementos na tela | 154.219 | 4.860 |
| Reconstrução completa + layout | 2.246 ms | 132 ms |

Uma consulta sem mudanças levou 1,9 ms no ensaio, com **zero bytes de corpo, dois SELECTs e nenhuma gravação**. Ela não reconstrói o funil. A preparação inicial dos resumos dessa base levou cerca de 1,5 segundo no ensaio, além da inicialização e criação dos índices; é feita uma vez e o resultado persiste nas reinicializações. Depois, somente dados alterados são recalculados.

A contagem de consultas foi medida separadamente dos tempos. A API usa mediana de cinco leituras após preparar os resumos; o diagnóstico anterior usou três leituras. O ensaio de interface mede três reconstruções e aguarda dois quadros para layout, em uma janela de 1440×1000. O estado sem mudanças e a preservação de cards durante alterações são verificados separadamente no navegador real.

## Validação

216 testes locais passaram, com os dois testes exclusivos de Windows ignorados no Linux. A cobertura nova inclui paginação, totais completos, buscas fora da página, atualização privada por carteira, transferência/exclusão/restauração, consulta sem gravação, datas que vencem sem mensagem nova, histórico com horários iguais, contadores incrementais, atualização futura do modelo e trabalhador ocioso sem bloqueio de escrita. A matriz de distribuição inclui PR, mantendo consumidores de PR com Grasi e todos os lojistas com Chai.

O ensaio Chromium cobre os fluxos existentes e as novas páginas, marcadores condicionais, atualização de outro card sem substituir um card inalterado, acesso à ficha fora da página e mensagens/atividades anteriores sem perder rascunho. A sintaxe JavaScript e os testes de privacidade do service worker são verificados antes da publicação.

A validação Windows e o pacote imutável serão registrados junto da ativação do canal. Os dados de clientes reais e os recursos de CPU/RAM/disco/rede do servidor da empresa não foram acessados neste ambiente. Não houve contato com leads reais ou alterações nas credenciais Meta.

## Aplicar no servidor

Use **Sais Blue CRM → Atualizar e abrir CRM**. Depois, **recarregue o navegador em todos os computadores e aparelhos da equipe**, para carregar a interface nova. Não é necessário baixar outro executável, apagar contatos ou recriar o banco.

O endereço externo continua http://200.225.129.156:3001. Executável, inicialização do Windows, supervisor e túnel permanecem como estavam. O atualizador mantém os backups e o mecanismo de restauração existentes.
