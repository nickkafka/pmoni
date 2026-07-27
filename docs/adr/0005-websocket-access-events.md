# ADR 0005 — Distribuição de eventos de acesso por WebSocket

**Status:** Aceito  
**Data:** 2026-07-24

## Decisão

A rota `WS /ws/access-events` é consumidora do `DeviceManager`. Cada conexão recebe sua própria fila de eventos e somente mensagens serializadas do contrato interno `AccessEvent`.

O endpoint não acessa banco de dados, Sigma ou Hikvision. Se o monitoramento não foi configurado, ele comunica `monitoring_unavailable` e fecha a conexão.
