# Sais Blue CRM — atualização 2026.11.06.4

## Aplicar no servidor Windows

Abra o aplicativo **Sais Blue CRM** e clique em **Atualizar e abrir CRM**. O atualizador faz backup, preserva os dados e a configuração e reinicia a instalação. Atualize a página; o rodapé deve mostrar **2026.11.09.3**. Não é necessário reinstalar nem parar as janelas manualmente.

## Acesso de Chai e Grasi

Na mesma rede da empresa, elas abrem **http://192.168.0.219:3000** no navegador. Não precisam instalar o CRM, Python ou ngrok.

O administrador abre o CRM nesse endereço, entra em **Equipe**, informa o e-mail real de cada uma, escolhe **Membro** e gera um convite individual. Compartilhe o link com a pessoa correspondente; cada uma cria seu nome e senha. O convite vale por 48 horas, é usado uma vez e não é enviado por e-mail automaticamente. O servidor e o CRM precisam estar ligados.

O campo Responsável controla quem tem acesso: atendentes veem e editam apenas suas próprias oportunidades. Somente o administrador original vê toda a equipe e os cards sem responsável. Transferências são feitas pelo administrador.

## Ativar o roteiro e a distribuição

Após Chai e Grasi ativarem suas contas:

1. Como administrador, abra **Integrações → Primeiro atendimento automático**.
2. Marque **Ativar o roteiro para leads de anúncios**.
3. Selecione **Por perfil e estado · Chai / Grasi**.
4. No campo Chai, selecione a conta ativa de Chai. No campo Grasi, selecione a conta ativa de Grasi.
5. Clique em **Salvar primeiro atendimento**.

O assistente se apresenta, pergunta **1 — Lojista / 2 — Revenda / 3 — Consumidor Final**, depois pede **cidade/UF**, por exemplo **Guaporé/RS**. Salva o perfil como tag e a cidade do catálogo de municípios, usada no mapa. O roteiro é fixo, sem serviço externo de IA. A automação começa desativada na atualização e não envia perguntas em massa aos contatos antigos.

| Perfil confirmado | UF confirmada | Responsável |
| --- | --- | --- |
| Lojista ou Revenda | RS ou SC | Chai |
| Lojista ou Revenda | Demais estados | Grasi |
| Consumidor Final | Qualquer estado, inclusive RS e SC | Grasi |

Respostas não identificadas recebem uma nova orientação. Após duas respostas inválidas na mesma pergunta, ou se o cliente pedir **ATENDENTE**, o card passa a atendimento humano. Dados não confirmados continuam pendentes; a localização não é adivinhada. Se a conta de destino for desativada, a atribuição fica pendente, com registro no histórico.

## Assumir ou transferir um atendimento

Abra o card e clique em **Assumir atendimento** para atribuir a si mesmo e pausar as perguntas automáticas. Para transferir, selecione a pessoa em **Encaminhar para** e clique em **Encaminhar atendimento**. Funciona mesmo com cidade/UF ainda pendentes. A equipe pode completar/corrigir o perfil e a localização na ficha.

Uma resposta enviada pelo CRM também pausa a qualificação. O aplicativo WhatsApp Business continua funcionando; os envios feitos diretamente no aplicativo não são sincronizados por eventos de eco nesta versão. Antes de continuar pelo celular um contato em qualificação, use **Assumir atendimento** no CRM para pausar o roteiro.

## Anúncios, tags e funil

- Novos contatos são admitidos por referência de anúncio recebida da Meta: `source_type=ad` com identificação, ou identificador de clique `ctwa_clid`. Uma referência de publicação comum não admite o contato.
- Texto “vim do anúncio” e links comuns para WhatsApp não comprovam origem. Nenhuma mensagem de uma conversa orgânica não admitida é gravada no CRM. O cadastro manual explícito é a única exceção à admissão por anúncios.
- As próximas mensagens de um lead admitido continuam no histórico mesmo sem repetir a referência de anúncio. O anúncio de origem é preservado.
- Os cadastros que já existiam são preservados. Esta atualização não apaga contatos ou conversas anteriores. O botão **Nova oportunidade** permite cadastro manual explícito, com origem Manual, sem robô e com recebimento apenas das próximas mensagens daquele número; a simulação de anúncio continua disponível somente nos ambientes que a habilitam, sem envio real.
- Tags **Lojista**, **Revenda** e **Consumidor Final** aparecem no card e nos contatos. O seletor **Todos os perfis** filtra funil, atendimento, contatos, mapa e indicadores. A **Visão geral → Resultados por perfil** separa leads, oportunidades abertas, valor em negociação, vendas e valor ganho. Cadastros sem classificação aparecem como perfil pendente.
- A etapa **Proposta enviada** foi removida. Cards anteriores nessa etapa passam a **Negociação**, com registro no histórico. O restante do card e as mensagens são preservados.

## Validar após a atualização

1. De um número novo, envie uma mensagem comum ao WhatsApp oficial: não deve criar card nem receber o roteiro.
2. Entre pelo **anúncio publicado** e envie a mensagem. O card deve registrar a origem e receber a pergunta de perfil.
3. Responda **Lojista** e **Guaporé/RS**: tag Lojista, município no mapa e responsável Chai.
4. Com outro lead de anúncio, responda **Consumidor Final** e **Florianópolis/SC**: responsável Grasi.
5. Confira tags, filtro e resultados por perfil. Atribua o atendimento à conta correspondente e confirme que somente essa atendente e o administrador conseguem acessar o card.

As perguntas são registradas em fila no banco e enviadas pelo processo do CRM. Eventos repetidos não geram perguntas duplicadas. Timeout/interrupção pode ocorrer após a Meta aceitar o envio: o sistema registra **Sem confirmação**, passa à equipe e não reenvia automaticamente. Falha de entrega informada pela Meta também fica no histórico. O roteiro respeita a janela de atendimento de 24 horas; templates fora dela não fazem parte desta versão.

Os testes locais usam mensagens e transporte Meta simulados. A atualização só estará ativa no servidor da empresa após aplicar o pacote, configurar as duas contas e validar os testes reais acima. O piloto atual depende de manter o servidor, o CRM e a conexão HTTPS em funcionamento.
