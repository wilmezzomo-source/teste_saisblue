# Editar nomes e receber avisos — 2026.11.09.4

No servidor Windows, abra **Sais Blue CRM → Atualizar e abrir CRM**. Depois, cada pessoa recarrega a página e confere **2026.11.09.4** no rodapé. A atualização preserva contatos, contas, responsáveis, configuração do WhatsApp e histórico.

## Corrigir o nome do cliente

1. Abra a ficha do contato e clique em **Editar nome**, ao lado de Chamar no WhatsApp.
2. Informe o nome confirmado e clique em **Salvar nome**.

Essa correção pode ser feita mesmo enquanto a cidade/UF ainda está pendente. O nome não pode ficar vazio e aceita até 120 caracteres. A alteração fica no histórico; as mensagens seguintes do WhatsApp não substituem o nome corrigido pelo nome do perfil.

O administrador pode editar qualquer oportunidade ativa. Atendentes podem editar apenas as próprias oportunidades. Corrigir o nome não inicia, interrompe ou reinicia o roteiro de qualificação.

## Ativar os avisos com som

1. Na parte superior do CRM, clique em **Avisos**.
2. Clique em **Ativar avisos com som**. Um toque confirma a ativação.
3. Mantenha o CRM aberto no navegador. Cada atendente faz essa ativação no próprio aparelho.

Os popups visuais aparecem mesmo com o som desativado. O navegador exige uma interação para liberar o áudio; após reabrir a página, um clique no CRM pode liberá-lo novamente. Se necessário, abra Avisos e clique em Ativar avisos com som. A preferência é guardada por conta e navegador; o botão Desativar som permite desligá-la.

Os avisos não funcionam com o navegador fechado. Esta versão usa popups dentro do CRM e um toque local, sem depender de envio de mensagens para o WhatsApp da equipe.

## Quem recebe

- O administrador recebe avisos de novos contatos admitidos no CRM. Novos contatos sem responsável continuam visíveis apenas para ele.
- A atendente recebe o aviso quando a oportunidade é atribuída à conta dela, inclusive após a qualificação automática. Transferências e restaurações também geram aviso para quem passa a atender.
- Cadastros manuais feitos pela própria pessoa não geram aviso para ela mesma. Se outra pessoa cadastrar ou atribuir uma oportunidade para a atendente, ela recebe o aviso.
- Conversas comuns que não tenham origem de anúncio ou admissão manual continuam fora do CRM e não geram avisos.

A distribuição permanece: **Lojista/Revenda de RS ou SC → Chai; Lojista/Revenda dos demais estados e todo Consumidor Final → Grasi**.

## Consultar e abrir

O contador em Avisos mostra os não lidos. O popup oferece **Ver oportunidade**, que abre a ficha e marca o aviso como lido. **Dispensar aviso** fecha apenas o popup; o registro continua na lista. Também é possível usar **Marcar todas como lidas**.

Os avisos independem dos filtros de perfil e responsável e não apagam o que está sendo digitado em uma ficha. Na primeira abertura, os avisos anteriores ficam na lista sem uma sequência de popups ou sons antigos. Avisos de cards que saíram do acesso da pessoa ou foram excluídos deixam de aparecer para ela.

O som pode ser agrupado quando várias oportunidades chegam na mesma consulta. Eventos repetidos da Meta não criam avisos duplicados. As consultas ocorrem a cada poucos segundos com o CRM aberto; o navegador pode reduzir a frequência em segundo plano.

## Validação

Os testes cobrem permissões por responsável, marcação de leitura por usuário, deduplicação, persistência após reinício, transferências, exclusão/restauração e correção do nome antes da cidade. O teste de navegador também verifica a ativação e execução do áudio, o popup durante a digitação sem perder o rascunho, a abertura da ficha e a ausência de uma sequência de alertas antigos ao entrar.
