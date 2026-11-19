# Validação dos retornos finais e encerramento virtual — 2026.11.19.1

A última chamada regular agenda um retorno ativo: Lojista D14→D30, Revenda D10→D45 e Consumidor Final D7→D15. Os intervalos usam a data real do atendimento marcado e o próximo dia útil quando necessário. O retorno final aparece destacado no card, no sino e em Retornos. Após registrá-lo, o card entra na fila Avaliar resultado; a equipe decide Ganho ou Perdido manualmente.

A qualificação virtual sem resposta passa a Perdido com Sem Resposta nas Observações após 24h da última mensagem da cliente, desde que uma pergunta tenha sido enviada. Não exige que o servidor tenha completado todas as retomadas durante uma indisponibilidade. Não encerra atendimentos assumidos, agendas humanas registradas, cadastros manuais, outras etapas do funil, envios nunca realizados, falhas de entrega ou envios sem confirmação. A janela é renovada quando a cliente responde. Envios pendentes expirados são cancelados sem enviar mensagem extra.

## Verificação

A suíte local passou com 203 testes; os dois testes exclusivos de Windows foram ignorados no Linux. Há 23 cenários de acompanhamento e 27 de diálogo contextual, além da cobertura existente de distribuição, privacidade, duplicidade, atualização e servidor. Os testes confirmam os três retornos finais, atraso persistente, resultado manual, preservação de revisões personalizadas e histórico após reiniciar. O encerramento virtual cobre indisponibilidade, pergunta não enviada, falha, proteção de intervenção humana, renovação de janela, reabertura após resposta genuína e falha de entrega comunicada depois do encerramento.

O Chromium passou: D14 passou a D30 no sino, D7 passou a D15, marcar D15 levou a Avaliar resultado e a atendente marcou Perdido pela ficha. Nenhuma mensagem WhatsApp foi criada por essas ações. O rascunho de Observações permaneceu durante a marcação de etapas. A interface de 390px não apresentou rolagem horizontal. Os fluxos existentes de permissões, perfis, filtros, edição, mapa e notificações também passaram. O service worker e a sintaxe JavaScript passaram.

[Validação do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44597652466): 203 testes, sem falhas ou erros.
[Validação do canal publicado no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44598615951): 203 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.19.1, confirmou a versão em execução e preservou banco e configuração na instalação Windows isolada.

O pacote imutável é o commit `89ae740d718389045b1e17b32e601a716b3ea5f6`, SHA-256 `de61ca31f9bca708f4585427439cf0f3e46c6bda54f8cd7d82eaf8f9612e0417`, com 3.761.339 bytes. Todos os 146 arquivos rastreados foram comparados com o ZIP público. O pacote não contém banco, .env, chave privada ou diretório de execução.

## Preservação e aplicação

O executável, launcher, início automático do Windows, supervisor, túnel HTTPS e módulos de interpretação e localização permanecem iguais aos da versão 2026.11.17.2. Esta atualização não restaura a retomada em lote anteriormente cancelada. As perguntas, a cadência de mensagens e a distribuição de responsáveis continuam como estavam; a mudança no WhatsApp limita-se ao encerramento virtual em 24h e à proteção da agenda humana contra esse encerramento.

A antiga classificação visual Qualificação pendente deixa de ocultar cards cujo estado real é Perdido. Eventuais registros gravados diretamente nessa coluna antiga são devolvidos a Novo contato com auditoria, sem perder responsável ou agenda; o trabalhador virtual aplica a regra de perda apenas quando os critérios são satisfeitos. Contatos perdidos sem responsável continuam exclusivos do administrador.

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM**, depois recarregue o navegador. O acesso http://200.225.129.156:3001, o banco e a configuração são preservados. Não houve acesso ao servidor ou aos leads reais da empresa: os testes usam dados fictícios, transporte Meta simulado e uma instalação Windows isolada. O resultado não comprova que o servidor da empresa já aplicou o pacote.

Consulte [RETORNOS-E-LEMBRETES.md](RETORNOS-E-LEMBRETES.md).
