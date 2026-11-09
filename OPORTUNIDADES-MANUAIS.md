# Oportunidades manuais — 2026.11.09.4

No servidor Windows, abra o aplicativo **Sais Blue CRM**, clique em **Atualizar e abrir CRM** e atualize a página no navegador. Não é necessário reinstalar ou parar processos manualmente. O rodapé deve mostrar **2026.11.09.4**.

## Cadastrar uma oportunidade

1. Qualquer pessoa com conta ativa abre **Nova oportunidade**, no topo do CRM.
2. Preenche nome, WhatsApp com DDI (55 para Brasil), estado e cidade. Cidade/UF são obrigatórios.
3. Seleciona o perfil, etapa e valor. O administrador também escolhe o responsável. Pode acrescentar Instagram e observação.
4. Clica em **Adicionar ao CRM**. A ficha abre para conferência e edição.

A origem aparece como **Manual**, sem marcar o cliente como anúncio. O responsável inicial é a pessoa que está cadastrando. Para atendentes, essa atribuição é obrigatória e não pode ser trocada. O administrador pode escolher outra conta ativa ou deixar o card sem responsável. O perfil pode ficar “A identificar” até a equipe confirmar.

O cadastro manual não envia mensagem nem inicia o robô de qualificação. As próximas mensagens recebidas desse número oficial passam a ser registradas nessa ficha para atendimento humano. Conversas de outros números sem anúncio ou cadastro manual continuam fora do CRM. Mensagens antigas do WhatsApp não são importadas ao criar a oportunidade.

O mesmo telefone, inclusive formatado com espaços e parênteses, não cria dois cards. Se já existir, abra a oportunidade existente quando tiver acesso, ou peça ao administrador para conferir. Esta versão mantém uma oportunidade por telefone.

Para responder pelo CRM, o cliente precisa ter enviado uma mensagem recebida pela integração nas últimas 24 horas. Cadastrar um telefone não abre essa janela. O aplicativo WhatsApp Business continua disponível no celular.

## O que permanece

Leads de anúncios continuam recebendo o roteiro e a distribuição já configurados. A atualização preserva contas, senhas, contatos, configurações Meta, roteiro ativado e vínculos de Chai/Grasi. Os dados anteriores não são apagados nem passam a ter origem Manual automaticamente.

## Validação

Os testes verificam cadastro e edição apenas por quem tem acesso, cidade obrigatória, telefone duplicado, origem protegida, conservação das configurações, recebimento apenas do telefone cadastrado e ausência de respostas automáticas mesmo com o robô de anúncios ligado. O teste em navegador também cobre a criação por uma conta de membro.

## Acesso por responsável

- O administrador original (Willian) vê todas as oportunidades, inclusive as sem responsável, e distribui ou transfere os atendimentos.
- Grasi e Chai veem apenas os cards atribuídos às suas contas. A restrição vale no funil, contatos, conversas, mensagens, notas, mapa e indicadores, e também nas chamadas diretas à API.
- O cadastro manual feito por uma atendente é atribuído à própria conta, sem iniciar o robô. Ela não pode se atribuir um card de outra pessoa ou pegar um card sem responsável.
- Ao transferir uma oportunidade, o acesso anterior é revogado. A próxima consulta remove o card da tela da atendente anterior e fecha uma ficha que tenha ficado aberta. Dados já vistos anteriormente não podem ser desvistos; a proteção vale para o acesso após a atualização/transferência.
- Novos convites são de atendentes. Contas administrativas adicionais passam a atendentes; a conta administrativa original permanece com acesso geral.
- Os responsáveis já cadastrados são associados às contas existentes. Se houver dois usuários com o mesmo nome ou nenhum usuário correspondente, o card permanece visível só ao administrador até ele escolher a conta correta. A autorização usa o identificador da conta, nunca apenas o nome.

Após atualizar, cada pessoa deve recarregar o navegador. As permissões do servidor valem inclusive para sessões que já estavam abertas; não é preciso redefinir senhas.

## Filtrar por responsável e perfil

Como administrador, escolha uma conta em **Todos os responsáveis** e um perfil em **Todos os perfis**. Por exemplo: **Grasi + Revenda** mostra somente as revendas atribuídas a Grasi.

Os dois filtros funcionam juntos no funil, contatos, atendimento, mapa e indicadores. **Sem responsável** também pode ser combinado com Lojista, Revenda, Consumidor Final ou Perfil pendente. Voltar para **Todos os responsáveis** preserva o perfil escolhido; voltar para **Todos os perfis** preserva a responsável escolhida. As seleções são mantidas ao trocar de aba enquanto a página estiver aberta.

O filtro de responsável aparece apenas para o administrador. Atendentes continuam com acesso somente às próprias oportunidades.

## Cards no funil

O preview mostra a tag do perfil e uma etiqueta colorida com o nome da responsável. A origem do contato e a situação da qualificação ficam dentro da ficha, sem ocupar o card. A distribuição permanece: Lojista/Revenda de RS e SC para Chai; Lojista/Revenda dos demais estados e todo Consumidor Final para Grasi.

## Excluir e restaurar cards

Apenas o administrador abre a ficha e usa **Excluir card**, confirmando o nome do cliente. O card vai para **Lixeira** e sai do funil, atendimento, contatos, mapa e indicadores. A exclusão pausa o roteiro e cancela perguntas ainda na fila. Enquanto estiver na lixeira, novas mensagens desse número são ignoradas, inclusive novos cliques em anúncio.

Para recuperar, abra **Lixeira → Restaurar card**. O histórico, os dados e a responsável são preservados, e o atendimento permanece humano. Atendentes não podem excluir, restaurar ou consultar a lixeira. Se um telefone já estiver na lixeira, restaure o card em vez de criar outro.

A lixeira não apaga definitivamente os dados pessoais. Solicitações de exclusão de dados seguem o canal informado na política de privacidade. Uma mensagem já em envio pode chegar mesmo após o card ser movido; a exclusão impede novos envios da fila e o início de novas perguntas.

## Chamar no WhatsApp

Na ficha de qualquer oportunidade disponível para sua conta, clique em **Chamar no WhatsApp**. O botão abre uma nova aba com o link oficial `wa.me`, já com o telefone do cliente e DDI. O sistema e o navegador permitem seguir para o aplicativo instalado ou WhatsApp Web. A conta usada é a que estiver conectada no aparelho da atendente; conecte o WhatsApp da Sais Blue para atender pelo número da empresa.

Esse atalho abre a conversa e preserva a ficha do CRM na aba atual. O envio acontece no WhatsApp, sem registrar uma mensagem fictícia no CRM nem mudar o responsável. Se o roteiro automático ainda estiver ativo na ficha, use **Assumir atendimento** antes de continuar por fora do CRM.
