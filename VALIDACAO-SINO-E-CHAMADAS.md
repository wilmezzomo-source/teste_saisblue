# Validação do sino e chamadas no card — 2026.11.17.2

O card oferece um sino com a próxima chamada e caixinhas para registrar o atendimento realizado. Marcar D3 hoje agenda D7 pelo intervalo de quatro dias, ajustado para o próximo dia útil quando necessário. Etapas anteriores não são inventadas. Chamadas não realizadas permanecem atrasadas, com tag vermelha, até uma ação da equipe.

## Verificação

A suíte local passou com 198 testes, com dois testes exclusivos do Windows ignorados no Linux. Os 22 cenários de acompanhamento cobrem início direto em D3 sem formulário prévio, atraso persistente, datas calculadas a partir da atividade real, sequência após retorno combinado, reinício sem inventar conversa, revisão após última etapa, pausa ao receber resposta e resposta no mesmo segundo. A migração do formato anterior preserva histórico e identifica respostas novas.

Os testes da qualificação pendente confirmam: ausência de perfil e localização, ausência de responsável, 24h desde a primeira mensagem e tentativas virtuais esgotadas. Perfil ou localização informados, atendente atribuído ou tentativas ainda em curso impedem essa classificação. O administrador continua sendo o único que vê os pendentes sem responsável. Atendentes não recebem nem a coluna nem acesso por ID a esses contatos.

O Chromium passou com uma atendente real do ambiente de teste: marcar D3 no card, obter D7, abrir o sino, escolher uma data vencida e ver ATRASADO em vermelho, filtrar os atrasados, agendar Hoje e filtrar Chamar hoje. Foram verificados período inclusivo, limpeza do período, combinação de perfil e responsável e consulta atualizada ao abrir a agenda. Registrar D7 preservou um rascunho não salvo nas Observações da ficha. O fluxo móvel em 390px passou sem rolagem horizontal no documento. Os testes existentes de CRM, WhatsApp, duplicidade, acesso e notificações continuaram passando. O service worker e a sintaxe JavaScript passaram.

[Validação do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44153982606): 198 testes, sem falhas ou erros.

[Validação do canal publicado no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44155336978): 198 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.17.2, confirmou a versão em execução e preservou banco e configuração na instalação Windows isolada.

O pacote imutável é o commit `b554cbf1ff072631806b4cff292581b19d2054db`, com SHA-256 `43459a00f2be6b5c7c14266a6a0e228d1e05b7a2a4ebe9153997ad609ada2e09` e 3.757.639 bytes. Os 145 arquivos rastreados foram comparados com o ZIP público. Não há banco, .env, chave privada ou diretório de execução.

## Preservação e limites

Os módulos de qualificação do WhatsApp, launcher, executável, início do Windows e túnel foram comparados com a versão 2026.11.17.1 e permanecem iguais. Registrar atividade não modifica as mensagens, os dados de qualificação, a responsável ou a etapa do funil. Os testes comparam esses registros antes e depois. Não há retomada de clientes em lote ou mensagem de WhatsApp gerada por uma caixinha.

As opções de negociação, revisão, não contato e recompra permanecem em Mais opções de acompanhamento. Os dados existentes são preservados. Para calcular o intervalo seguinte, vale a data efetiva do atendimento realizado; o registro de início é mantido quando já existia. A data combinada pode substituir a sequência. Não é necessário preencher a última conversa para registrar uma etapa no card.

O acesso externo informado, http://200.225.129.156:3001, e as credenciais Meta não foram alterados. Não houve acesso à instalação Windows ou aos contatos reais da empresa. Os testes usam dados fictícios e transporte Meta simulado. A entrega no iPhone continua dependente de HTTPS e validação no aparelho.

As consultas solicitadas às páginas oficiais do Kommo e RD Station foram bloqueadas pelo gateway deste ambiente com erro 403. Não se afirma ter consultado as interfaces desses serviços; o desenho implementado concentra tarefa, prazo, conclusão e atraso no próprio card.

## Aplicar

No servidor, use Sais Blue CRM → Atualizar e abrir CRM e depois recarregue o navegador. Marque a etapa realizada no card ou clique no sino para escolher uma data. Consulte [RETORNOS-E-LEMBRETES.md](RETORNOS-E-LEMBRETES.md).
