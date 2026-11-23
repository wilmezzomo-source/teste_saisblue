# Validação de desempenho e distribuição — 2026.11.23.1

A interface usa resumos paginados de 30 cards por coluna/lista; mensagens e auditoria são buscadas na ficha. Indicadores, busca e filtros continuam abrangendo toda a base autorizada. Consultas sem alterações recebem 304 sem corpo, por carteira e dia de Brasília. No funil, elementos de cards inalterados são preservados e os demais são atualizados ou movidos. As contagens do histórico são incrementais. O trabalhador ocioso consulta a fila sem adquirir bloqueio de escrita a cada segundo, inclusive com o assistente desativado e temporizadores antigos.

A distribuição automática agora inclui **Revenda de PR → Chai**, junto com Revenda de RS/SC e todo Lojista. Demais Revendas e todo Consumidor Final continuam com Grasi; PL/WL permanece com o administrador original. Atribuições manuais e contatos orgânicos permanecem como estavam. A atualização não inicia uma retomada em lote ou muda os textos do assistente.

## Testes

A suíte local passou com 216 testes; dois casos exclusivos de Windows foram ignorados no Linux. Os testes novos cobrem paginação/totais completos, consultas fora da página, cache privado por carteira, transferência/exclusão/restauração, leitura sem UPDATE, vencimentos sem mensagem nova, cursores com horários iguais, contagens ao inserir/editar/mover/excluir mensagens, atualização futura do modelo derivado, verificação do administrador original e trabalhador ocioso. A matriz regional testa Curitiba/PR e consumidores de PR com Grasi; um teste de produção confirma que uma pergunta nova acorda o trabalhador sem esperar a manutenção.

O Chromium passou na interface real com os fluxos existentes e as novidades: 35 oportunidades com 30 na primeira página e 5 na segunda, total completo no cabeçalho, atualização de outro contato preservando o mesmo elemento de um card inalterado, consulta sem mudanças preservando o funil, ficha aberta fora da página e 105 notas consultadas em páginas de 100 e 5. O carregamento de mensagens e auditoria anterior preservou a Observação não salva. Os testes de privacidade, filtros combinados, atrasos, marcação de chamadas e interface de 390px continuaram passando. A sintaxe JavaScript e o service worker passaram.

[Validação do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/45198875534): 216 testes, sem falhas ou erros.

[Validação do canal público no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/45200165397): 216 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.23.1, confirmou a versão em execução e preservou banco e configuração na instalação Windows isolada.

## Medição controlada

Na base fictícia de 5.000 contatos, 100.000 mensagens e 50.000 eventos de auditoria, a lista passou de 71,03 MB e 33.254 SELECTs para **228.625 bytes e 20 SELECTs**. O tempo mediano da API local passou de 2.418,9 ms para 28,3 ms com o modelo preparado. Uma leitura sem mudanças levou 1,9 ms, sem corpo, com dois SELECTs e sem gravações. A preparação inicial do modelo levou cerca de 1,5 segundo no ensaio e permanece armazenada.

O navegador passou de 5.000 para 150 cards presentes no funil, com 4.860 elementos em vez de 154.219 e acesso aos demais por páginas. Reconstrução completa e layout passaram de 2.246 ms para 132 ms. São ensaios locais Linux/Chromium, não medições do Windows da empresa ou do link externo. O detalhamento e o método estão em [DESEMPENHO-CRM.md](DESEMPENHO-CRM.md) e o diagnóstico inicial em [DIAGNOSTICO-DESEMPENHO-2026-11-23.md](DIAGNOSTICO-DESEMPENHO-2026-11-23.md).

## Pacote e preservação

O pacote imutável usa o commit `be0c18a812bae07ab1f69398737d2cdc0446744e`, SHA-256 `5b140b95ca8b68268762cedc31564914430a66906e35f0a07afc22a031c436a1`, com 3.786.537 bytes. Os 152 arquivos rastreados foram comparados com o ZIP público, incluindo workspace.py e public/workspace.js. Não há banco, .env, chave privada, diretório de execução ou o módulo de recuperação em lote cancelado.

O banco recebe índices e tabelas auxiliares de leitura, preservando registros e histórico originais. O cache é invalidado por inserções, mudanças de responsável, atualizações e exclusões. Uma versão futura do aplicativo reconstrói o modelo derivado para refletir alterações de regras. A autenticação continua verificando o administrador original por leitura.

Executável, inicialização do Windows, supervisor, launcher, controle dos processos, túnel e credenciais não foram alterados. O acesso externo permanece http://200.225.129.156:3001. Não houve acesso ao servidor ou a leads reais; os testes usam dados fictícios, transporte Meta simulado e uma instalação Windows isolada.

Para aplicar, use **Sais Blue CRM → Atualizar e abrir CRM** no servidor e recarregue os navegadores da equipe. Reabra o app no celular para carregar a interface nova. A confirmação dos testes e da publicação não comprova que o servidor da empresa já aplicou o pacote.
