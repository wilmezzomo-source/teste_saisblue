# Filtro por etapa — 2026.11.23.2

Mapa e Contatos compartilham o seletor **Todas as etapas**, junto dos filtros de perfil, responsável e próxima chamada. O filtro é aplicado antes da paginação, incluindo os totais e contatos sem localização no Mapa. A seleção é lembrada entre as duas abas e não limita o funil ou Retornos quando fica oculta. O parâmetro anterior de etapa do Mapa continua aceito pelo servidor.

## Verificações concluídas

- Suíte local: 217 testes, sem falhas; dois casos exclusivos de Windows ignorados no Linux.
- [Código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/45260418882): execução concluída com sucesso, incluindo os 217 testes e a compilação do aplicativo.
- Chromium: combinação etapa/perfil/responsável, seleção compartilhada Mapa/Contatos, totais e pins, filtro oculto sem limitar o funil, carteira privada da atendente e tela de 390px. A suíte existente de paginação, histórico, rascunhos e lembretes também passou.
- API: contatos fora da primeira página, localizados e sem cidade; etapa combinada com perfil/responsável/data; totais completos e isolamento entre responsáveis.
- Sintaxe JavaScript, privacidade do service worker e diferenças de arquivos verificadas.

Os testes usam dados fictícios. A execução Windows do código ainda usa o canal anterior nos testes que baixam uma instalação publicada; ela não comprova instalação da versão nova no servidor da empresa.

## Publicação

O canal público `windows-release.json` oferece **2026.11.23.2**, com o commit imutável `fd8ab1a63f5f64855bacea9c27899c60631a769c` e SHA-256 `b3b8e3a6ef83cbc7fcf648e4e76e94ee66d9c56b1e9584d525b96848e8fc555a`.

O ZIP público tem 3.791.669 bytes. Os 154 arquivos rastreados desse commit foram comparados, byte a byte, com o conteúdo do pacote. Não contém banco, .env, chave privada ou dados de execução. O manifesto público foi baixado e comparado com o local, e seu hash foi conferido com o ZIP.

A ativação do canal aciona outra execução automática do Windows. Seu resultado deve ser consultado no GitHub Actions; o sucesso citado acima corresponde à validação do código, anterior à ativação.

Para aplicar, use **Sais Blue CRM → Atualizar e abrir CRM** no servidor e recarregue os navegadores da equipe. Não houve acesso ao servidor ou aos contatos reais da empresa. Esta alteração não muda atendimento WhatsApp, distribuição de leads, lembretes, credenciais, portas ou início do Windows.
