# ADR 0001 — Eventos normalizados e credenciais de dispositivos

**Status:** Aceito  
**Data:** 2026-07-24

## Contexto

O pMoni recebe eventos de fabricantes diferentes e armazena credenciais de equipamentos cadastrados.

## Decisão

- `AccessEvent` é o contrato normalizado de entrada: inclui `external_id`, `device_id`, `employee_no`, resultado e horário. Não contém dados de apresentação do morador.
- `EnrichedAccessEvent` associa opcionalmente um `ResidentSummary` local para consumo pela interface.
- Adaptadores de fabricantes implementam `DeviceClient`, que entrega somente `AccessEvent`.
- A tabela de dispositivos armazena somente `credentials_encrypted`; a chave Fernet é fornecida em `DEVICE_CREDENTIALS_KEY` e não é persistida.

## Consequências

Adicionar um fabricante não altera o fluxo de domínio. O cadastro de dispositivos exige uma chave de proteção configurada. Bancos legados com uma coluna `password` devem ter as credenciais reinseridas após uma migração assistida, em vez de copiar senhas em texto aberto.

As alterações de schema são aplicadas exclusivamente pelo Alembic; a API não executa `create_all` na inicialização.
