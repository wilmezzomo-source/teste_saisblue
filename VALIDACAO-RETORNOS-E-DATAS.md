# Validação de retornos, datas e acesso externo — 2026.11.17.1

A atualização acrescenta uma agenda interna com sequências por perfil, registro da última conversa, progresso das tentativas, data combinada, negociação ativa, revisão e ciclo de recompra. Inclui a coluna de Qualificação pendente e filtros inclusivos de data combinados com perfil e responsável. Não envia WhatsApp.

## Verificação

A suíte local passou com 192 testes, com dois testes nativos do Windows ignorados no Linux. Os 16 cenários de acompanhamento cobrem sequências, D0 persistente, prazos vencidos, fim da sequência, revisão, data combinada, negociação sem expiração por idade, resposta do cliente, opt-out, recompra, expediente, validação, reinício, concorrência e permissões. A marcação de uma tentativa real antes das 9h é permitida no próprio dia; o aviso continua respeitando o expediente.

Os três testes de acesso externo validam login e escrita em http://200.225.129.156:3001, links de equipe, preservação do acesso LAN, CSRF, recusa de outras portas/origens e ausência de alteração das credenciais Meta. São testes isolados de aplicação, sem conexão à instalação da empresa.

O Chromium passou com o formulário de acompanhamento, as cinco etapas de Lojista, mudança para retorno combinado e filtros de data, perfil e responsável juntos. O intervalo com início igual ao fim inclui o dia escolhido; um intervalo sem correspondência esvazia a lista e Limpar datas restaura os resultados. Foi verificado o filtro pela última conversa, a nova coluna e ausência de rolagem horizontal na agenda em 390px. Os testes existentes de CRM, acesso restrito, duplicidade, qualificação e notificações continuaram passando. O service worker e a sintaxe JavaScript passaram.

[Validação do código no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44142680622): 192 testes, sem falhas ou erros.

[Validação do canal público no Windows](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/44143622701): 192 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.17.1, confirmou a versão em execução e preservou banco e configuração na instalação Windows isolada.

O pacote imutável é o commit `a791b12832c20166f31c61c1206a727c2b7b9b1e`, com SHA-256 `8ee5b13c933d5ad0496e3fe72a3dce06815e79ead9c8984737f832beffbe55ac` e 3.750.335 bytes. Os 144 arquivos rastreados foram comparados com o pacote. Não há banco, .env, chave privada ou diretório de execução.

## Preservação e limites

Os arquivos qualification.py, qualification_dialogue.py, qualification_location.py, automatic_start.py, supervise_crm.py, desktop_worker.py, iniciar_https.py e o executável do atualizador foram comparados com a versão anterior e são iguais. O launcher reconhece apenas a nova chave opcional CRM_ACCESS_URL; a porta interna permanece 3000. A fila de WhatsApp, seus estados e os registros de qualificação não são alterados pelo salvamento ou execução dos lembretes. Um teste compara os registros completos antes e depois do acompanhamento e confirma essa preservação. Não há retomada em lote.

A coluna automática de Qualificação pendente é uma classificação da exibição interna, sem reescrever o estado usado pelo bot. Os avisos internos são restritos à responsável atual ou ao administrador quando não existe responsável, deduplicados e cancelados quando não cabem mais. O envio Web Push revalida a pertinência do lembrete e a permissão antes de despachar.

Não houve acesso ao banco, ao Windows ou aos contatos reais da empresa. A consulta ao IP externo foi recusada pelo gateway deste ambiente com 403 Domain forbidden; não confirma disponibilidade ou falha do CRM real. O endereço HTTP informado pelo usuário é usado como origem externa exata e nos links da equipe. HTTPS configurado não é rebaixado para HTTP. Instalação como app e notificações de tela bloqueada no iPhone continuam exigindo HTTPS, configuração e teste no aparelho.

O expediente inicial é de segunda a sexta, das 9h às 18h de Brasília, sem calendário de feriados. Datas combinadas são preservadas. As faixas de recompra usam o ciclo preenchido pela equipe; nenhuma data de compra histórica é inventada. O servidor precisa permanecer ligado para gerar os avisos.

## Aplicar

No servidor, use **Sais Blue CRM → Atualizar e abrir CRM** e recarregue o navegador. Na ficha, informe a última conversa e salve o acompanhamento; marque cada tentativa efetivamente realizada. Use Retornos para consultar as datas e a fila de revisão. Consulte [RETORNOS-E-LEMBRETES.md](RETORNOS-E-LEMBRETES.md).
