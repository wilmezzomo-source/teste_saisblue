# Validação do atendimento com contexto — 2026.11.13.1

O reconhecimento local aproveita intenção, respostas separadas e localização dentro de frases, sem chave, créditos ou API de IA. Não é um modelo GPT rodando no servidor. Reconhece uso próprio, início de revenda e os termos White Label / Private Label / PL / WL; dúvidas comuns recebem resposta breve sem inventar condições comerciais.

Marca própria é encaminhada ao administrador original, Willian. Marca e volume mensal são perguntados antes do encaminhamento e gravados nas Observações, preservando notas da equipe. Esses dados são opcionais: a cliente pode não saber, pedir continuidade com uma consultora ou deixar de responder. Após a pergunta enviada, a espera de 15 minutos encaminha com os dados disponíveis; fora de 24 horas só há atualização interna, sem mensagem de WhatsApp. O perfil tem etiqueta, filtro e linha nos indicadores, com a mesma restrição de acesso das demais oportunidades.

O encerramento em Perdido com Sem Resposta exige todas as quatro retomadas do ciclo aceitas/enviadas sem falha conhecida e 24 horas sem resposta. Não atinge atendimento assumido, intervenção manual, perda manual, pedido de interrupção ou sequência incompleta. Uma nova resposta pode reabrir apenas uma perda automática ainda não revisada pela equipe. Falha de entrega recebida depois desfaz o encerramento automático para revisão humana, sem repetir o envio.

## Verificação

A [execução Windows do código](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43483635042) passou com os 147 testes, incluindo os testes nativos do aplicativo e da inicialização automática. A suíte local também passou: 147 descobertos, dois exclusivos do Windows ignorados no Linux. Há 23 cenários adicionais de conversa contextual, marca própria, dados opcionais e encerramento conservador.

A [execução de ativação do canal](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/43484481045) também passou: 147 testes, sem falhas ou erros. O executável entregue baixou e instalou a versão 2026.11.13.1 do canal público, preservou dados e configuração e confirmou o início automático e o controle dos processos do CRM em uma instalação Windows isolada.

O Chromium validou a interface final, incluindo perfil de marca própria, privacidade por responsável e Observações em várias linhas que sobrevivem ao salvamento de outros campos. Os testes existentes de edição sem localização, funil, anúncios, filtros, mapa, avisos e visualização móvel passaram. O teste do service worker e as verificações de sintaxe JavaScript passaram.

O pacote imutável é o commit `68c2a12e641330022547825d8431ee09c54342b7`, com SHA-256 `c1b3db4af9ed479d95084086395053100a7849c597f6f4fb4845896455afd514` e 3.713.262 bytes. Módulos e executável foram comparados com os arquivos locais. O pacote não inclui banco, `.env`, chaves privadas ou arquivos de execução. O manifesto público foi conferido contra o arquivo local e o hash do ZIP.

## Aplicar

No servidor Windows, abra **Sais Blue CRM → Atualizar e abrir CRM**. Depois recarregue o CRM nos navegadores da equipe. Não é necessário configurar uma API de IA. Os testes usam dados fictícios e transporte Meta simulado; a instalação na empresa e o atendimento real precisam ser confirmados após aplicar a versão naquele servidor.
