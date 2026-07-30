# ADR 0006 — Adaptador Hikvision por consulta ao journal de acesso

**Status:** Aceito  
**Data:** 2026-07-27  
**Substitui:** [ADR 0003](0003-hikvision-isapi-alert-stream.md)

## Contexto

O ADR 0003 assumiu que o adaptador Hikvision receberia eventos por uma conexão
persistente em `/ISAPI/Event/notification/alertStream`. A verificação contra um
DS-K1T342MFWX real mostrou que terminais de controle de acesso não expõem esse
recurso: a rota responde HTTP 404. O equipamento oferece, no lugar, a consulta ao
journal em `POST /ISAPI/AccessControl/AcsEvent`.

Três características do firmware foram medidas no equipamento e determinam o desenho:

- O nonce do Digest deixa de ser aceito depois de cerca de trinta segundos. O
  `httpx` continua assinando com o nonce vencido e trata o `401` como resposta
  final, o que interrompia a consulta após poucos minutos.
- O campo `serialNo` é monotônico por dispositivo e pode ser filtrado por
  `beginSerialNo`/`endSerialNo`, e `searchResultPosition` aceita salto direto para
  a última posição informada por `totalMatches`.
- Datas com microssegundos são recusadas com `badJsonContent`.

## Decisão

`HikvisionClient` implementa `DeviceClient` consultando o journal periodicamente.
Ao conectar, o cursor é posicionado no `serialNo` mais recente já registrado — em
uma única consulta, via salto de posição — de modo que o histórico não é reemitido.
Cada ciclo pede apenas as entradas posteriores ao cursor e pagina enquanto o
equipamento indicar `MORE`.

`IsapiSession` concentra o transporte e refaz o handshake Digest quando uma
resposta `401` chega, tornando a expiração do nonce invisível para o adaptador.

Somente entradas que identificam uma pessoa (`employeeNoString`) viram
`AccessEvent`. Em amostragem distribuída por todo o journal do equipamento, apenas
o código `minor` 75 identificou pessoas; os demais descrevem a porta ou rejeições
anônimas. `ACCESS_GRANTED_MINOR_CODES` lista os códigos aceitos como liberação e é
o ponto de extensão quando outros forem observados em produção.

O nome que o equipamento envia no evento é descartado: o ADR 0001 mantém dados de
apresentação fora do `AccessEvent`, e eles serão fornecidos pelo enriquecimento.

## Consequências

O restante do sistema permanece inalterado — `DeviceManager`, WebSocket e domínio
continuam consumindo `AccessEvent` sem conhecer ISAPI. A entrega deixa de ser
instantânea e passa a ter a latência do intervalo de consulta, aceitável para uma
tela de portaria.

A alternativa de notificação ativa (`/ISAPI/Event/notification/httpHosts`), que
entrega a foto da captura junto do evento, exige que o pMoni seja alcançável
pela rede do equipamento e altera a configuração dele. Fica registrada como
evolução possível atrás da mesma porta `DeviceClient`, sem impacto no domínio.

A foto do momento da passagem não está disponível hoje: o equipamento está com
`pictureServerType` em `null`, então `pictureURL` chega vazio e `AccessEvent.snapshot`
permanece nulo. A foto usada na interface virá do cadastro biométrico, sincronizado
à parte.
