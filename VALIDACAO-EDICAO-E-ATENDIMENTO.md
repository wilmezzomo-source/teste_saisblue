# Edição livre e atendimento — 2026.11.12.1

## Alterações

A edição da oportunidade e o movimento entre etapas não dependem de cidade/UF. O formulário sinaliza esses campos como opcionais e o servidor aceita alterações de perfil, nome, responsável, valor, observação, Instagram e etapa sem localização. A UF pode ser salva antes da cidade; dados de localização inalterados não são reenviados com outras edições. Se a equipe limpar a localização, o card permanece disponível e sem pin até selecionar um município válido. O cadastro manual mantém a regra de criação anterior.

O reconhecimento de perfil inclui “comprar para mim”, “comprar pra mim”, “pra meu uso” e “para eu usar” como Consumidor Final. A finalidade explícita da compra tem prioridade sobre uma profissão mencionada, como “tenho loja, mas quero comprar para mim”. Negações e finalidades explícitas conflitantes são tratadas sem adivinhar o perfil.

A confirmação de conclusão é: **Seu atendimento foi registrado. Em breve, uma consultora entrará em contato com você por aqui.** A distribuição continua registrada internamente. A mesma confirmação substitui mensagens automáticas antigas ainda na fila; não altera mensagens já enviadas nem repete envios sem confirmação.

## Verificação

**Windows: 124 testes aprovados, sem falhas ou erros.** O código passou na [execução 43281570087](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43281570087). A atualização pelo executável entregue, baixando a versão 2026.11.12.1 do canal público, passou na [execução 43282549424](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43282549424), incluindo preservação do banco/configuração e recuperação automática. O manifesto público foi conferido com o commit e o SHA-256 do pacote.

A suíte contém 124 testes. São verificados todos os estágios sem localização, edição por administradores e atendentes autorizadas, preservação de UF parcial, limpeza de localização, catálogo válido, conflito de revisão e bloqueio de cards alheios. A qualificação usa transporte Meta simulado para verificar uso próprio, encaminhamento interno e confirmação neutra, inclusive mensagens antigas em fila.

O Chromium valida a ficha sem campos de localização obrigatórios, a edição de perfil e outros dados, eventos de arrastar e soltar, UF sem cidade e preenchimento posterior. Os testes existentes também cobrem mapa, acesso restrito, anúncios, atribuição, notificações, exclusão e restauração e visualização móvel. O teste do service worker passou.

O pacote imutável é o commit `19a7c8ea4dc310f014cc536365390c358cf2b2f7`, com SHA-256 `3ca135f5f462197fc9f290cc46527e01522d78cc3614f117bd6146277a87c066` e 3.696.669 bytes. Os módulos e o executável foram comparados com os arquivos locais; o pacote não inclui banco, `.env`, chaves privadas ou arquivos de execução.

## Aplicar

No servidor Windows: **Sais Blue CRM → Atualizar e abrir CRM**. Depois, recarregue a página do CRM nos computadores da equipe para carregar a interface sem o bloqueio. A instalação na empresa e o envio real no WhatsApp só podem ser confirmados após aplicar a atualização naquele servidor; os testes não usam credenciais ou contatos reais.
