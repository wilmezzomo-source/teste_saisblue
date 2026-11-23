# Etapa no Mapa e em Contatos — 2026.11.23.2

Abra **Mapa** ou **Contatos** e use **Todas as etapas**, no topo junto de perfil, responsável e data. Escolha Novo contato, Em atendimento, Negociação, Ganho ou Perdido. Para remover o filtro, volte a Todas as etapas.

A seleção é mantida ao alternar entre Mapa e Contatos. O filtro não é aplicado de forma oculta nas demais abas: o funil e Retornos continuam usando seus próprios controles. No Mapa, o seletor antigo da barra interna foi substituído pelo controle do topo, evitando duas seleções conflitantes.

O filtro é aplicado no servidor antes da paginação e combina com perfil, responsável, busca e próxima chamada. Totais e indicadores consideram todos os resultados autorizados, não somente a página visível. No Mapa, a etapa também limita os contatos com localização pendente. O estado/UF do mapa mantém o comportamento anterior: filtra os pins sem esconder contatos cuja localização ainda é desconhecida.

Cada atendente continua acessando apenas a própria carteira. O administrador original mantém a visão global. Nenhum card é movido de etapa por esse seletor. Roteiro e distribuição do WhatsApp, permissões, lembretes, dados e desempenho da listagem foram preservados.

## Verificação

O teste de API usa contatos localizados e sem cidade, em etapas diferentes e de responsáveis diferentes. Confere uma etapa cujos registros estão fora da primeira página, soma correta, combinação com perfil/responsável/data e compatibilidade com o parâmetro anterior do mapa. O teste de navegador verifica o mesmo seletor nas duas abas, manutenção da seleção ao alternar entre elas, totais/pins, acesso restrito da atendente, ausência de filtro oculto no funil e tela de 390px.

O código passou em 217 testes no Windows, na interface Chromium e nas verificações do service worker. O pacote e o canal público foram conferidos. Veja [VALIDACAO-FILTRO-POR-ETAPA.md](VALIDACAO-FILTRO-POR-ETAPA.md) para as evidências e os limites dessa validação.

## Aplicar

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM**. Depois, recarregue os navegadores da equipe. No celular, feche e reabra o app.

O acesso externo continua http://200.225.129.156:3001. O mesmo executável é usado, sem alteração no início do Windows ou nas credenciais. Não houve acesso aos contatos reais da empresa nesta implementação.
