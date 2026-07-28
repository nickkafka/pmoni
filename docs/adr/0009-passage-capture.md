# ADR 0009 — Captura da passagem exibida ao lado da foto de cadastro

**Status:** Aceito  
**Data:** 2026-07-28

## Contexto

Os equipamentos configurados para guardar a imagem da passagem publicam um
`pictureURL` em cada evento. A tela do porteiro passa a mostrar essa captura ao
lado do retrato do cadastro, para que ele compare quem passou com quem deveria
passar.

A URL publicada não serve ao navegador: o equipamento informa o endereço pelo qual
ele conhece a si mesmo — um endereço de rede local mesmo quando o acesso é por
DDNS — e ainda acrescenta um token por requisição. Além disso o download exige
autenticação Digest, que a interface não possui nem deve possuir.

## Decisão

O adaptador reduz o `pictureURL` ao caminho, como já fazia com a foto de cadastro,
e baixa a imagem pela própria sessão autenticada no momento em que o evento é
coletado — enquanto o equipamento ainda a serve. A imagem vai para `SnapshotStore`,
e a interface a obtém em `GET /access-events/{device_id}/{external_id}/snapshot`.

`InMemorySnapshotStore` guarda as capturas mais recentes e descarta as antigas. Uma
captura só interessa enquanto a passagem está na tela, então não é persistida: uma
reinicialização simplesmente recomeça a coletar.

Quando o download falha, o evento é publicado sem captura em vez de ficar retido.
Saber que alguém passou vale mais do que a imagem daquela passagem.

## Consequências

Cada evento com captura custa um download adicional ao ser coletado — cerca de
0,15s nos equipamentos em rede local. O evento só é publicado depois disso, o que
garante que a imagem esteja disponível quando a tela pedir.

A captura é um quadro grande-angular, com a pessoa onde a câmera a pegou, muitas
vezes perto de uma borda. Por isso ela é exibida inteira, e não recortada para o
formato do retrato: o recorte centralizado removia justamente o rosto.

Equipamentos sem armazenamento de imagem configurado seguem funcionando; seus
eventos apenas não trazem captura.
