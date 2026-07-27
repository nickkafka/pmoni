# ADR 0003 — Adaptador Hikvision por ISAPI Alert Stream

**Status:** Aceito  
**Data:** 2026-07-24

## Decisão

`HikvisionClient` implementa `DeviceClient` com HTTP Digest e uma conexão persistente em `GET /ISAPI/Event/notification/alertStream`. O adaptador suporta notificações XML, JSON e partes multipart. Cada notificação é convertida por `HikvisionAlertParser` para `AccessEvent`; heartbeats e mensagens inválidas são descartados.

`HikvisionClientFactory` obtém a credencial cifrada por uma porta específica, descriptografa apenas durante a construção do cliente e entrega o cliente ao `DeviceManager`.

## Consequências

O restante do sistema não conhece ISAPI, HTTP, XML ou JSON da Hikvision. Uma notificação malformada não encerra o stream. Falhas de conexão continuam sendo tratadas pela política de reconexão do `DeviceManager`.
