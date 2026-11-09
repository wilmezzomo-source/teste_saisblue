# Validação — 2026.11.09.5

Código publicado em `5b4475b8fa021029a735d6426c149fa7a846a3eb`, na branch autorizada `crm-windows`. O manifesto público fixa esse commit e o SHA-256 `cca98a44f345f75bf193e678c5d96e75c54f44ddc5695c5234ca2e193434678f` do ZIP. O binário público do atualizador foi comparado ao compilado entregue. Nenhum `.env`, banco de clientes ou chave privada entrou no pacote.

Validações locais concluídas em 9/11/2026:

- Python: 85 testes, com o teste exclusivo do Windows omitido no Linux; todos os demais passaram. Incluem atribuição e transferência, acesso privado, qualificação de anúncios, deduplicação, cancelamento de envios, expiração, tentativas limitadas e inscrição de aparelhos.
- Chromium real: fluxo existente do CRM, avisos e sons, versão exibida, manifesto, registro do service worker, ausência de cache das APIs, retorno ao card depois de login por link de aviso e página offline sem contatos.
- Service worker: avisos genéricos, links limitados ao próprio CRM e ausência de interceptação/cache de APIs.
- Criptografia Web Push: o envio real da biblioteca foi exercitado com transporte local simulado; o corpo sai criptografado e inclui autenticação VAPID. Nenhum provedor real foi acionado nesses testes.
- Caddy 2.11.9 oficial: checksum SHA-512 conferido e configuração do domínio aceita pelo validador. Um teste com certificado local validado exerceu HTTPS → Caddy → Waitress, login, Origin/CSRF, cookie Secure e bloqueio de dados sem login. Esse teste local não configura DNS nem comprova acesso ao servidor da empresa.

O [teste Windows do código e do executável](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/42682685321/job/129381139256) passou. A [checagem do canal final](https://github.com/wilmezzomo-source/teste_saisblue/actions/runs/42683324323/job/129383398031) também passou em Windows: exercitou o executável entregue e o pacote 2026.11.09.5 baixado pelo atualizador.

A ativação no servidor da empresa, DNS na Telium, encaminhamento no roteador, certificado público e recebimento real em um iPhone bloqueado dependem da aplicação e validação descritas em [IPHONE-E-ACESSO-EXTERNO.md](IPHONE-E-ACESSO-EXTERNO.md). Não foram realizados remotamente nesta sessão. O assistente gera a solicitação concreta para Telium/TI; as credenciais Meta e o callback atual permanecem preservados.
