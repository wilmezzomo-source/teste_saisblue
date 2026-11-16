# Validação do bloqueio de telefones duplicados — 2026.11.16.2

A correção parte da versão restaurada de 13/11. O roteiro de qualificação, a retomada cancelada e o código do atualizador não foram alterados. O pacote não contém `qualification_recovery.py`.

O cadastro manual compara telefones globalmente, incluindo oportunidades de outra atendente e cards na lixeira. A consulta ocorre na mesma transação de escrita que cria a oportunidade. Formatação, prefixo internacional 00, DDI brasileiro e variações de celular com/sem nono dígito não permitem outro cadastro do mesmo número. O identificador de WhatsApp já gravado não é reescrito.

Novos números brasileiros digitados só com DDD recebem o DDI 55. Registros históricos sem DDI também são considerados na recusa do cadastro. A indicação interna do formato dos novos cadastros diferencia números internacionais explícitos de uma sequência nacional brasileira semelhante. Telefones fixos não recebem a equivalência do nono dígito.

Uma mensagem da Meta com a variação brasileira de celular é vinculada à oportunidade existente sem criar outro card ou reativar o bot sobre uma admissão manual. O bloqueio não revela nome, responsável ou identificador de um card ao qual a atendente não tem acesso. O formulário mantém o preenchimento e mostra o erro junto ao WhatsApp; alterar o número limpa o erro e permite tentar novamente.

## Verificação

A [validação nativa do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43880667445) passou com 158 testes, sem falhas ou erros.

A [validação do canal publicado](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43881689053) também passou com 158 testes. O executável entregue baixou e instalou a versão 2026.11.16.2, confirmou a versão em execução e preservou banco e configuração em uma instalação Windows isolada.

A suíte local passou: 158 testes descobertos, com dois exclusivos do Windows ignorados no Linux. Os 11 cenários adicionais cobrem variações de formatação/DDI/nono dígito, anúncios, continuidade de cadastro manual, oportunidade de outra atendente, lixeira, dados históricos, cadastros simultâneos, telefone fixo e distinção entre países. Duas atendentes e um administrador tentando variantes simultaneamente criam apenas uma oportunidade; os demais recebem HTTP 409.

O Chromium passou com o fluxo de cadastro duplicado: o formulário permanece aberto, os dados digitados são preservados, o telefone recebe o erro e a edição do número limpa a validação. Os testes existentes de funil, qualificação, filtros, permissões, mapa, notificações e visualização móvel continuaram passando. O service worker e a sintaxe JavaScript passaram.

O pacote imutável é o commit `d95733dd6b544701451619b15315288dd95d5cf2`, com SHA-256 `b77a4fe442cc48b3fa13709604033257d25cb6c395815801e5620b55c20d5af2` e 3.720.804 bytes. Módulos, interface e executável foram comparados aos arquivos locais. Não há banco, `.env`, chaves privadas ou arquivos de execução no pacote. O executável e o código de início do Windows continuam iguais aos da versão restaurada.

## Aplicar

A instalação na empresa precisa receber o pacote pelo aplicativo existente. Depois de atualizar, recarregue o navegador para carregar a validação do formulário. Não há fusão ou exclusão automática de duplicidades históricas. Os testes usam dados fictícios; não acessam nem alteram os contatos reais da empresa.
