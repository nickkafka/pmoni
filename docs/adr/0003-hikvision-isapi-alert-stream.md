# ADR 0003 — Adaptador Hikvision por ISAPI Alert Stream

**Status:** Substituído pelo [ADR 0006](0006-hikvision-acs-event-polling.md) em 2026-07-27  
**Data:** 2026-07-24

> O Alert Stream não existe nos terminais de controle de acesso: o DS-K1T342MFWX
> responde HTTP 404 em `/ISAPI/Event/notification/alertStream`. A decisão abaixo
> ficou restrita a câmeras e NVRs, que o Monikraft não integra.

## Decisão

`HikvisionClient` implementa `DeviceClient` com HTTP Digest e uma conexão persistente em `GET /ISAPI/Event/notification/alertStream`. O adaptador suporta notificações XML, JSON e partes multipart. Cada notificação é convertida por `HikvisionAlertParser` para `AccessEvent`; heartbeats e mensagens inválidas são descartados.

`HikvisionClientFactory` obtém a credencial cifrada por uma porta específica, descriptografa apenas durante a construção do cliente e entrega o cliente ao `DeviceManager`.

## Consequências

O restante do sistema não conhece ISAPI, HTTP, XML ou JSON da Hikvision. Uma notificação malformada não encerra o stream. Falhas de conexão continuam sendo tratadas pela política de reconexão do `DeviceManager`.
