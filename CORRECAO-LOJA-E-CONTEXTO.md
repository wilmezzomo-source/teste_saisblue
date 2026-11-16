# Loja e contexto da conversa — 2026.11.16.3

“Loja”, “LOJA”, “para loja”, “para loja que estou abrindo”, “estou abrindo uma loja” e expressões semelhantes identificam **Lojista**. A apresentação da cliente não precisa usar o termo técnico “lojista”. Negativas, perguntas sobre a existência de uma loja e finalidade explícita de uso próprio continuam sendo consideradas para evitar atribuir o perfil errado.

A preposição “para” em frases de compra não preenche mais a UF Pará. Estados informados expressamente continuam válidos, assim como municípios cujo nome contém Pará. Uma confirmação da UF por extenso não troca um município já reconhecido por uma cidade com o nome do estado.

O assistente aproveita cidade/UF informadas antes do perfil. Quando falta o perfil, pode consultar as últimas mensagens recebidas dessa mesma cliente na janela de atendimento, mesmo quando a resposta anterior ocorreu há mais de dois minutos. Essa consulta ocorre ao processar uma nova mensagem da cliente. Não inicia uma retomada em lote, não altera atendimentos assumidos ou concluídos e não ativa o início automático do Windows.

Exemplo esperado: **Estou abrindo uma loja → pergunta apenas a cidade; Gaspar SC → Lojista, Gaspar/SC, Chai**. Se Gaspar/SC já estiver registrado, a resposta sobre a loja conclui o encaminhamento sem perguntar a localização outra vez. O card permanece em Novo contato, e a confirmação não divulga o nome da responsável. Após concluir, não continuam os lembretes da qualificação.

Outro exemplo verificado: **Prô meu uso → Consumidor Final; Cláudio Minas Gerais, horas depois → Cláudio/MG, Grasi**. Uma dúvida sobre preço de atacado não altera uma finalidade de uso próprio já informada. A pergunta fica no histórico para a consultora, sem inventar quantidade mínima ou condições comerciais.

Os testes reproduzem esses cenários com dados fictícios e transporte Meta simulado. Só é possível aproveitar mensagens que tenham sido recebidas pelo CRM. Mensagens que ficaram apenas no celular durante uma indisponibilidade e não foram entregues pela Meta não são recuperadas por essa correção. Respostas manuais feitas só pelo celular continuam sem sincronização de eco nesta integração; para registrar a pausa do assistente, a equipe deve assumir o atendimento no CRM.

A proteção de telefones duplicados da versão 2026.11.16.2 é mantida. O código do atualizador e do início do Windows não foi modificado nesta versão.
