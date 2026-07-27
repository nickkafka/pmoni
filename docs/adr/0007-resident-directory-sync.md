# ADR 0007 — Diretório local de moradores sincronizado do equipamento

**Status:** Aceito  
**Data:** 2026-07-27

## Contexto

A tela do porteiro precisa exibir a foto de cadastro, o nome e o apartamento de
quem passa na facial. O equipamento entrega apenas identificador, nome e a foto do
cadastro — o que o Sigma exporta para ele. O número do apartamento não existe no
equipamento: `roomNumber` e `floorNumber` estavam zerados nas 55 pessoas cadastradas
e `PersonInfoExtends` vazio.

A foto do momento da passagem não é uma alternativa: além de depender de um servidor
de imagens não configurado, um retrato de cadastro identifica melhor a pessoa do que
uma captura contra a luz.

## Decisão

O Monikraft mantém uma tabela `residents` própria, sincronizada do equipamento e
chaveada por `employee_no` — o mesmo identificador que o Sigma exporta, e portanto a
junção natural quando aquela integração existir.

A sincronização divide a posse dos campos: `name` e `photo` pertencem ao equipamento
e são sobrescritos a cada execução; `apartment` e `block` pertencem ao Monikraft e
nunca são tocados pela sincronização. Isso permite cadastrar o apartamento pela
interface administrativa agora e trocar essa origem pelo Sigma depois, sem migração.

As fotos são gravadas como BLOB na própria linha do morador. O volume é pequeno
(55 fotos ocupam cerca de 2 MB) e evita coordenar arquivos soltos com o banco, o que
importa em uma aplicação desktop distribuída com o SQLite junto.

Uma foto só é rebaixada quando ainda não existe localmente ou quando o cadastro
biométrico mudou, comparando o caminho estável da imagem — sem o host e sem o token
por requisição que o firmware acrescenta.

## Consequências

A interface consome `GET /residents/{employee_no}/photo` sem falar com o equipamento,
o que mantém a tela rápida e funcional mesmo com o equipamento fora do ar.

Duas peculiaridades do firmware ficam contidas no adaptador: a busca de rostos
devolve três registros por página e informa `OK` mesmo com páginas restantes, então
ambas as buscas paginam por `totalMatches`. Confiar em `responseStatusStrg`
truncaria o diretório silenciosamente em três pessoas.

Pessoas cadastradas em mais de um equipamento ocupam uma única linha, porque
`employee_no` é único. Isso pressupõe que os identificadores venham de uma origem
comum, como é o caso quando o Sigma exporta para todos os equipamentos.
