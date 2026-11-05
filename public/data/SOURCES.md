# Cartografia e municípios

- Catálogo: [Municípios Brasileiros — Kelvin S. do Prado](https://github.com/kelvins/Municipios-Brasileiros), arquivo `csv/municipios.csv`, obtido em 2026-11-05, 5.571 registros. Licença MIT preservada em CITIES-LICENSE. Inclui código IBGE, UF, nome e coordenadas da sede municipal. As coordenadas são referências de município; não localizam um cliente no seu endereço.
- Limites estaduais: [Click That 'Hood / Code for America](https://github.com/codeforamerica/click_that_hood/blob/master/public/data/brazil-states.geojson), 27 feições. Geometria simplificada para visualização nacional e coordenadas arredondadas a quatro casas. Licença preservada em MAP-LICENSE.
- Mapa interativo: Leaflet 1.9.4, licença BSD-2-Clause em `../vendor/leaflet/LICENSE`. Biblioteca distribuída localmente para não depender de CDN na instalação.
- Camada de ruas: [OpenStreetMap](https://www.openstreetmap.org/copyright), tiles de `tile.openstreetmap.org`. Atribuição exibida no mapa. Carregamento em tempo real, sem download em lote ou cache offline. O navegador precisa de acesso à internet para esta camada. Os limites estaduais e pins funcionam sem a camada de ruas.

A aplicação não envia os nomes, telefones ou Instagram dos leads a serviços de geocodificação. As coordenadas são resolvidas no servidor pelo catálogo local. As requisições de tiles revelam ao provedor os locais visualizados e o IP do navegador, como em outros mapas online.
