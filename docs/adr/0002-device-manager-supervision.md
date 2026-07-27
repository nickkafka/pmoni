# ADR 0002 — Supervisão isolada de dispositivos

**Status:** Aceito  
**Data:** 2026-07-24

## Decisão

O `DeviceManager` usa somente `DeviceRepository`, `DeviceClientFactory` e `DeviceClient`. Para cada dispositivo habilitado, ele cria uma tarefa assíncrona de supervisão que conecta, consome o fluxo de `AccessEvent`, desconecta e tenta reconectar após falhas.

Os consumidores se inscrevem em filas independentes. Quando uma fila atinge seu limite, o evento mais antigo é descartado para preservar a atualização mais recente e impedir que um consumidor lento bloqueie a recepção dos demais.

## Consequências

Falhas de um equipamento não interrompem outros dispositivos. WebSocket e enriquecimento de moradores serão consumidores do gerenciador, sem dependência do protocolo de fabricante. A fábrica concreta de clientes será implementada junto ao adaptador Hikvision, com acesso controlado às credenciais descriptografadas.
