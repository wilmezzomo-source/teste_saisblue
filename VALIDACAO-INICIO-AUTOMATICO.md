# Início automático e recuperação — 2026.11.11.1

O atualizador registra uma tarefa específica da instalação no Agendador do Windows. Ela usa S4U e a conta original com direitos limitados, sem senha armazenada e sem depender de sessão interativa. O consentimento local de administrador é solicitado pelo próprio Windows durante a primeira ativação. A conta recebe permissão de alteração apenas na instalação; não é usada uma tarefa SYSTEM para executar o CRM.

O monitor verifica a aplicação, o gateway e o agente. Reinicia processos identificados desta instalação, recupera o agente que ficou órfão após queda do gateway e espaça novas tentativas até cinco minutos. Não encerra processos desconhecidos. A trava de atualização impede reinício durante backup, cópia e recuperação; o atualizador aguarda uma verificação em andamento. A parada manual é persistida e respeitada mesmo após reiniciar o monitor.

## Pacote

- Commit: `f232a716190942022909f50232192084fdd8b25a`.
- ZIP público: 3.691.219 bytes.
- SHA-256: `edb4115267b164d11960d6777b0ca81804b461fadbf1af1f76d49ea3da6a2068`.
- Executável entregue e módulos conferidos contra o ZIP imutável. Sem banco, `.env`, chaves privadas ou arquivos de execução.

## Verificações

**Windows: aprovado, 120 testes, sem falhas ou erros.** A validação do código está na [execução 43014552198](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43014552198). A instalação da versão 2026.11.11.1 pelo executável entregue, usando o canal público já ativado, passou na [execução 43015344579](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43015344579). O teste do service worker também passou.

A suíte contém 120 testes. Os testes Windows criam uma instalação isolada, usam o executável entregue e exercitam download/conferência do canal público, atualização, preservação de banco e configuração, criação do atalho e parada restrita aos processos da instalação. A outra verificação cria uma pasta com permissões de administrador, ativa a tarefa pelo mesmo fluxo de elevação do atualizador e valida a execução com direitos limitados.

Na tarefa real do Windows, são provocadas quedas do processo da aplicação e do gateway, deixando o agente órfão. Confere-se a recuperação sem duplicar o agente nem encerrar um Python independente, além de parada manual e retomada. O ciclo do monitor é acelerado apenas na instalação fictícia de teste. Nenhuma credencial Meta/ngrok real é usada e nenhuma mensagem é enviada a clientes.

Os testes locais passaram: suíte Python, Chromium para login, cards, atendimento, filtros, atribuição, notificações e versão; service worker para privacidade dos avisos e links.

## Aplicar no servidor

Abra **Sais Blue CRM → Atualizar e abrir CRM**. Na primeira ativação, autorize o pedido local do Windows. Confira **Início automático e recuperação de falhas ativados**. Se a ativação for negada, o CRM continua disponível pelo aplicativo, e a janela informa a pendência; **Iniciar / reconectar** permite tentar novamente.

Não houve acesso ao Windows da empresa nem reinicialização física daquele servidor. A tarefa com gatilho de inicialização foi executada pelo Agendador em uma sessão de lote no Windows isolado. A causa da indisponibilidade relatada e a restauração da entrega real na empresa não estão confirmadas por esses testes. Servidor desligado, internet indisponível, IP alterado, limite da conta ngrok ou credenciais Meta inválidas exigem resolver a causa correspondente.
