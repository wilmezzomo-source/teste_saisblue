# Validação de loja e contexto — 2026.11.16.3

A atualização reconhece as respostas sobre loja e uso próprio e aproveita respostas anteriores recebidas da mesma cliente. Corrige a confusão entre a preposição “para” e o estado Pará. Não acrescenta API paga, retomada em lote ou mudança no início do Windows.

## Conversas verificadas

- “Estou abrindo uma loja” e “Para loja” identificam Lojista. “Gaspar SC”, antes ou depois do perfil, conclui como Gaspar/SC e Chai, mantendo Novo contato.
- “Prô meu uso”, seguido horas depois de “Cláudio Minas Gerais”, conclui como Consumidor Final, Cláudio/MG e Grasi.
- “para uso”, seguido horas depois de “Apucarana/ Paraná”, conclui como Consumidor Final, Apucarana/PR e Grasi. Repetir “para uso próprio” depois da conclusão não reinicia as perguntas.
- Uma dúvida sobre atacado não muda uma finalidade já informada de uso próprio. Não são inventados preços ou quantidade mínima.
- Uma resposta já recebida com a automação desativada pode ser aproveitada quando chega uma nova mensagem da cliente. Ativar a opção, sozinho, não dispara uma retomada em lote.
- Negativas, finalidades conflitantes, nomes reais de cidades com Pará, a confirmação do estado por extenso e admissão somente por anúncio continuam cobertos.

## Verificação

A suíte local passou em 173 testes, com dois testes exclusivos do Windows ignorados no Linux. Os 15 métodos adicionais reproduzem os erros de perfil, localização e contexto apresentados nas imagens e verificam a interrupção dos lembretes após concluir.

O Chromium passou nos fluxos completos de loja, Cláudio/MG e Apucarana/PR, com webhook assinado e transporte Meta simulado. Os testes existentes de cadastro sem duplicidade, permissões, filtros, notificações, edição e celular também passaram. O service worker e a sintaxe JavaScript passaram.

[Validação do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43939588315): 173 testes, sem falhas ou erros.

[Validação do canal público no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43940563616): 173 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.16.3, confirmou a versão em execução e preservou banco e configuração na instalação Windows isolada.

O pacote imutável é o commit `a8fef95b0354c9b5a22f115aaf127667bd7e260d`, com SHA-256 `84853a877a423b9fc62b5edadf00793d1d2722b8ec76791ab0b58f3eef7b0548` e 3.729.065 bytes. Os 138 arquivos rastreados foram comparados com o pacote. Não há banco, `.env`, chaves privadas ou diretórios de execução. Os arquivos do atualizador e início do Windows continuam iguais aos da versão restaurada.

## Aplicar e limites

No servidor, abra o aplicativo Sais Blue CRM e use **Atualizar e abrir CRM**. Recarregue o navegador. Esta validação foi feita com contatos fictícios; não acessa nem modifica os contatos reais da empresa e não comprova entrega real pela Meta.

A consulta de contexto depende das mensagens recebidas pelo CRM, dentro da janela de atendimento. Uma mensagem que ficou apenas no celular durante a queda não é recuperada. Atendimentos já concluídos ou assumidos pela equipe não são reiniciados. Para pausar a automação por uma intervenção humana, registre a tomada do atendimento no CRM; respostas enviadas só pelo celular não são sincronizadas nesta integração.
