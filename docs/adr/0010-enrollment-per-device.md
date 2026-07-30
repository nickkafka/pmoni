# ADR 0010 — Cadastro chaveado pelo equipamento que emitiu o identificador

**Status:** Aceito  
**Data:** 2026-07-28  
**Corrige:** [ADR 0007](0007-resident-directory-sync.md)

## Contexto

O ADR 0007 assumiu que `employee_no` identificaria a mesma pessoa em qualquer
equipamento, porque o Sigma exporta os mesmos identificadores para todos. Com três
faciais em operação a premissa se mostrou falsa: equipamentos cadastrados
separadamente reaproveitam números para pessoas diferentes.

A medição nos equipamentos do condomínio mostrou o alcance do problema. Entre as
duas faciais alimentadas pela mesma origem, 54 identificadores coincidem e nenhum
diverge. Já a facial cadastrada à parte diverge em dois: o ID 2 nomeia uma pessoa
nela e outra nas demais.

A consequência era grave. A sincronização sobrescrevia nome e foto de quem já
ocupava aquele identificador, e o porteiro via o rosto de outra pessoa ao lado da
captura de quem realmente passou.

## Decisão

Um cadastro pertence ao equipamento que o emitiu: a tabela é chaveada por
`(device_id, employee_no)`, e o evento é resolvido pelo equipamento de onde veio.
Um identificador sozinho nunca nomeia uma pessoa.

Fotos e localização passam a ser endereçadas pelo identificador da linha, que é
inequívoco, em lugar do `employee_no`.

A interface administrativa agrupa os cadastros por identificador e nome, de modo
que quem está em várias faciais aparece uma vez só, com as faciais listadas. Ao
informar o apartamento, ele é gravado em todos os cadastros daquela pessoa. Quem
foi cadastrado com identificadores diferentes em cada equipamento aparece em linhas
separadas: sem uma origem comum, unificá-los seria adivinhação — exatamente o erro
que causou este defeito.

## A foto emprestada de outro equipamento

Equipamentos que gravam o rosto apenas como template biométrico deixam o cadastro
sem imagem (ADR 0007). Como o cadastro é por equipamento, uma passagem em uma dessas
faciais apareceria sem rosto mesmo havendo foto da mesma pessoa em outra.

A busca do morador passa a apontar para o cadastro que tem a imagem, de qualquer
equipamento, **exigindo identificador e nome iguais** — a mesma regra do agrupamento.
Emprestar por identificador apenas reintroduziria o defeito que este ADR corrige: nos
equipamentos em operação, o identificador 2 nomeia três pessoas diferentes.

A identidade exibida continua sendo a do cadastro de origem; apenas a imagem vem de
outro. Nos dados reais, isso recuperou 160 dos 164 cadastros sem foto, sem nenhuma
divergência entre nome e rosto.

## Consequências

A mesma pessoa ocupa uma linha por equipamento em que está cadastrada, o que
multiplica as linhas mas nunca troca a identidade de ninguém. Quando o Sigma
passar a alimentar todos os equipamentos, os identificadores convergem e o
agrupamento reduz naturalmente.

A migração preserva os apartamentos já digitados no cadastro em que foram
informados. Um apartamento que tenha sido digitado enquanto o identificador
apontava para a pessoa errada continua onde estava, e precisa ser conferido.

A sincronização também apaga os cadastros que o equipamento deixou de listar.
Sem isso, uma reexportação do Sigma que troque identificadores deixaria pessoas
fantasma na interface para sempre. A remoção só acontece depois de percorrer todo
o diretório e nunca quando o equipamento responde sem ninguém, para que uma falha
momentânea não esvazie o cadastro.
