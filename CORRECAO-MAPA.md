# Mapa — versão 2026.11.06.2

O mapa abre usando cartografia local de estados brasileiros e coordenadas dos municípios, com os pins e filtros do CRM. Esse modo não depende dos tiles de um provedor externo e não exibe imagens de bloqueio 403 do OpenStreetMap.

A opção **Ruas · OpenStreetMap**, no controle de camadas do canto superior direito, permite carregar a camada online. A requisição de imagens agora usa `strict-origin-when-cross-origin` para informar somente a origem da aplicação ao provedor; a política de privacidade dos demais recursos continua preservada. Isso corrige a ausência de Referer da configuração anterior, mas não garante que um provedor aceite todos os IPs/redes. Em erro de carregamento, a aplicação volta ao mapa local sem perder os pins.

Testes: navegador verifica que não há requisições externas de tiles no modo inicial, simula HTTP 403 ao habilitar ruas, confere o Referer sem dados do contato e confirma que os pins continuam no mapa. A suite de servidor também passou. Não foi validada a liberação do provedor na rede da empresa.

## Aplicar

Pare o CRM com Ctrl+C no terminal em que está rodando. Extraia a nova versão em outra pasta, execute **ATUALIZAR-NO-WINDOWS.cmd** nessa pasta nova e selecione a pasta original. O atualizador cria backup e preserva `.env`, banco e usuários. Depois execute **INICIAR-NO-WINDOWS.cmd** na pasta original e atualize a página do navegador.

A correção do mapa não altera a configuração LAN nem conecta a conta WhatsApp. Para o número oficial, continuam necessárias a autorização/habilitação compatível com o aplicativo Business, as credenciais e o webhook HTTPS público.
