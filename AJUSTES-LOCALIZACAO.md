# Cidade, estado, Instagram e mapa

## O que mudou

- Cidade e UF são obrigatórias no cadastro manual. Selecione a UF e um município do catálogo para evitar grafias diferentes e pins em lugares errados.
- O Instagram aceita `@usuario`, nome de usuário ou link de perfil do Instagram. É salvo como nome de usuário e aparece com link para abrir o perfil. Outros domínios e links de posts não são aceitos.
- A ficha do contato permite alterar a localização e o Instagram; os dados aparecem na lista de contatos e a cidade/UF aparece no card. A busca também considera cidade, UF e Instagram.
- A aba **Mapa** apresenta pins agrupados por município, com a contagem de leads. Clique no pin para ver e abrir cada ficha. Filtre por UF e etapa. O pin indica a sede do município, não o endereço do cliente.
- Leads sem localização ficam em uma lista de pendências no mapa, inclusive quando há filtro por estado; o sistema não inventa uma cidade pelo DDD.

## Contatos existentes e WhatsApp

A atualização adiciona colunas ao banco existente sem apagar contatos, conversas, usuários ou senhas. Contatos anteriores sem localização ficam sinalizados como pendentes. É necessário preencher cidade/UF antes de salvar alterações da oportunidade ou mover seu card.

Mensagens reais do WhatsApp são preservadas mesmo quando o cliente ainda não informou sua cidade: criar um cadastro pendente é necessário para não descartar o atendimento. A equipe deve completar a localização na ficha. A API do WhatsApp não informa automaticamente a cidade/UF no evento comum de mensagem. Notas e atendimento continuam disponíveis enquanto a localização é completada.

## Mapa real e conexão

Leaflet, municípios e limites estaduais são servidos pelo próprio CRM. Os pins usam coordenadas do catálogo local, sem transmitir nome/telefone/Instagram a uma API de geocodificação. A camada OpenStreetMap precisa de internet no navegador; se ela falhar, o mapa usa os limites estaduais locais. Fontes e licenças estão em `public/data/SOURCES.md`.

O catálogo contém municípios brasileiros. Se for necessário trabalhar com outros países, é preciso ampliar o modelo e a base geográfica. Os limites são simplificados para visão comercial, não para navegação ou delimitação jurídica.

## Atualizar o Windows

1. Faça um backup do banco conforme o roteiro de instalação.
2. Pare o CRM com Ctrl+C no terminal, ou pare a tarefa da aplicação se já estiver configurada.
3. Extraia a atualização e copie todos os arquivos e subpastas para a pasta original do CRM, substituindo o código. Preserve `.env`, `.venv` e a pasta raiz `data`, que contém o banco.
4. **Copie também a nova pasta `public/data`** (catálogo/mapa) e `public/vendor` (Leaflet). A pasta `public/data` é diferente da pasta raiz `data` do banco.
5. Execute `INICIAR-NO-WINDOWS.cmd` novamente ou reinicie a tarefa configurada. Atualize a página do navegador.
6. Confira uma ficha antiga, preencha cidade/UF e Instagram, salve e abra a aba Mapa.

## Identidade visual

O layout e as cores existentes foram preservados. A aplicação da logo e fonte exatas do site ainda depende de consultar `saisblue.com.br`, bloqueado pela política de rede do ambiente de desenvolvimento. A liberação dos hosts do site e dos tiles foi salva como rascunho de configuração do ambiente, não aplicada ao servidor Windows da empresa. Não foi adotada uma fonte arbitrária como se fosse a oficial.

## WhatsApp oficial

Foi confirmado que o número da empresa é usado no aplicativo WhatsApp Business. Isso não confirma cadastro na API oficial nem elegibilidade à coexistência. A conexão real continua dependendo de conta/app Meta, credenciais, webhook HTTPS e validação real; a atualização não remove, migra nem desconecta o número do aplicativo.
