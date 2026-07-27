# ADR 0008 — Enriquecimento de eventos antes da interface

**Status:** Aceito  
**Data:** 2026-07-27  
**Estende:** [ADR 0005](0005-websocket-access-events.md)

## Contexto

O equipamento identifica quem passou apenas pela matrícula. A tela do porteiro
precisa de nome, foto e apartamento, que vivem no cadastro local sincronizado
(ADR 0007). O ADR 0005 mantém o endpoint WebSocket fora do banco de dados, e o
ADR 0001 mantém dados de apresentação fora do `AccessEvent`.

## Decisão

`AccessEventEnricher` fica entre o `DeviceManager` e o WebSocket: consome o fluxo
neutro de `AccessEvent`, resolve a matrícula no cadastro local e republica
`EnrichedAccessEvent` para seus próprios assinantes. As duas restrições anteriores
seguem válidas — o endpoint continua sendo apenas um consumidor e os adaptadores
continuam sem conhecer o morador.

A distribuição para assinantes foi extraída para `EventBroadcaster`, usada tanto
pelo gerenciador quanto pelo enriquecimento, mantendo a política de descartar o
evento mais antigo quando um consumidor fica para trás.

Um evento é publicado mesmo quando a matrícula é desconhecida ou a consulta falha,
com `resident` nulo. A portaria precisa saber que alguém passou mesmo sem cadastro,
e uma falha de banco não pode interromper o monitoramento.

A consulta abre uma sessão curta por evento. Uma sessão longa continuaria servindo
as linhas já carregadas, e um apartamento editado pela API só apareceria após
reiniciar a aplicação.

## Consequências

A mensagem do WebSocket ganha o objeto `resident`, com `photo_url` apontando para
`GET /residents/{employee_no}/photo` quando há foto sincronizada. A interface monta
a tela inteira a partir de uma única mensagem, sem consultar o equipamento.

`ResidentSummary` passa a informar `has_photo`, evitando que a interface peça uma
imagem inexistente.
