# ADR 0004 — Runtime de serviços da aplicação

**Status:** Aceito  
**Data:** 2026-07-24

## Decisão

O `ApplicationRuntime` é criado uma vez pelo processo FastAPI. No startup, após validar as migrações, ele compõe repositório, proteção de credenciais, fábrica Hikvision e `DeviceManager`. No shutdown, encerra primeiro os supervisores de dispositivos e depois a sessão de banco.

Se `DEVICE_CREDENTIALS_KEY` não estiver configurada, a API sobe sem monitoramento e registra um aviso explícito. Isso permite operações administrativas sem reduzir a proteção de credenciais.
