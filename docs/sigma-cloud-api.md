# Estudo da API Sigma Cloud (Segware)

Levantamento feito em 2026-07-28 a partir das especificações OpenAPI publicadas,
para preencher automaticamente o apartamento dos moradores importados das faciais.

## Onde está a especificação

O Swagger UI é renderizado por JavaScript e não expõe nada ao ser baixado. As
especificações estão em `/v2/api-docs` (apesar do nome, o conteúdo é OpenAPI 3.0.1):

| API | Especificação |
| --- | --- |
| SIGMA Cloud REST API | `https://api.segware.com.br/v2/api-docs` — 187 rotas |
| SIGMA Cloud Access Control REST API | `https://api-access-control.segware.com.br/v2/api-docs` — 27 rotas |

## Autenticação

Ambas declaram um único esquema: `Authorization: Bearer <JWT>`.

Nenhuma das duas tem rota de login, autenticação ou emissão de token. O token de
integração é fornecido pela Segware fora da API — é preciso solicitá-lo ao suporte
deles informando a empresa. Ou seja, o pMoni apenas guarda e usa um token que
já existe; não há usuário e senha a trocar por sessão.

Isso tem duas consequências práticas: o token precisa ser guardado cifrado, como já
é feito com a senha das faciais, e não há renovação automática — quando expirar ou
for revogado, a importação falha e o operador precisa de uma mensagem clara.

## O caminho mais curto para o apartamento

`GET /v1/accounts/{accountId}/dwellers` na API principal devolve, em uma única
chamada, tudo o que precisamos por morador (`AccountDwellerV2DTO`):

| Campo | Tipo | Serventia |
| --- | --- | --- |
| `id` | inteiro | Identificador da pessoa no Sigma |
| `name` | texto | Nome |
| `unities` | lista de `BlockUnitDTO` | **Apartamento e bloco** |
| `commonEnroll` | inteiro | Matrícula — ver a questão em aberto abaixo |
| `federalRegister` | texto | CPF |
| `photoUrl` | texto | Foto no Sigma |

E `BlockUnitDTO` traz exatamente os dois campos que faltavam no pMoni:

```
block    (texto)    nome do bloco
blockId  (inteiro)
unit     (texto)    o apartamento, por exemplo "301"
unitId   (inteiro)
```

A API de controle de acesso chega ao mesmo resultado, mas em três chamadas
(`/people`, `/units`, `/blocks`) e ligando `pessoa_unidade[].unidade_id` à unidade
manualmente. A rota da API principal é preferível por ser uma chamada só e já vir
com o bloco resolvido.

## Descobrir a conta

- `GET /v1/accounts?searchParams=<termo>` na API principal (parâmetro obrigatório),
  devolvendo `AccountDTO` com `id`, `accountCode`, `tradeName`.
- `GET /v1/accessControl/accounts` na API de acesso lista as contas sem filtro, com
  `id`, `codigo` e `nome`.

A segunda serve bem para o operador escolher a conta em uma lista na interface, em
vez de digitar um número.

## O que foi verificado com o token real (2026-07-29)

O token de integração do Grupo Prever foi testado, somente com `GET`. Ele é válido
e a conta foi localizada, mas **nenhuma rota que devolve pessoas ou unidades é
autorizada**.

Primeiro achado: `583775` é o **`id`** da conta, não o `accountCode` — o código dela
é `1950`. E `GET /v1/accounts?searchParams=...` ignora o filtro, devolvendo as 252
contas da empresa; é preciso filtrar do lado de cá.

| Rota | Resultado |
| --- | --- |
| `GET /v1/accounts` | 200 — 252 contas |
| `GET /v1/accounts/583775` | 200 — endereço, contrato, responsável |
| `GET /v1/accounts/583775/scond/configs/dwellers` | 200 — configuração, sem dados |
| `GET /v1/accounts/583775/pgms` e `/partitions` | 200 |
| `GET /v1/accounts/{id}/dwellers` (v1, v2, v3, v5) | **403** |
| `GET /v4/accounts/{id}/dwellers` | **403** com os parâmetros completos |
| `GET /v1/accounts/{id}/dwellers/search` | **403** |
| `GET /v1/accounts/{id}/employees` | **403** |
| Todas as rotas de `api-access-control.segware.com.br` | **403** |

A v4 chega a responder 400 sem os parâmetros obrigatórios, o que faz parecer que ela
funcionaria — mas é apenas a validação acontecendo antes da checagem de permissão:
com `groupsAndUnits`, `types` e `globalAccessGroupId` preenchidos, ela também
responde 403.

O 403 se repete em todas as contas testadas, e não só na 583775, enquanto os demais
dados da mesma conta leem sem problema. Ou seja, é uma permissão faltando no usuário
de integração, não algo específico daquela conta nem do token estar vencido.

**Falta pedir à Segware** que esse usuário de integração possa ler moradores e
unidades. Vale citar as rotas exatas: `GET /v1/accounts/{accountId}/dwellers` na API
principal e `GET /v1/accessControl/accounts/{accountId}/people`, `/units` e `/blocks`
na API de controle de acesso.

## A questão em aberto que decide a viabilidade

**Qual campo do Sigma corresponde ao ID que a facial informa no evento?**

O pMoni casa o evento com o cadastro pelo `employeeNo` da facial. Para preencher
o apartamento automaticamente, é preciso saber qual campo do Sigma é esse mesmo
número. Há dois candidatos:

- `AccountDwellerV2DTO.id` — o identificador da pessoa
- `AccountDwellerV2DTO.commonEnroll` — chamado de matrícula, e portanto o nome mais
  provável para o que é exportado ao equipamento

A especificação não diz qual deles é exportado, e não dá para decidir isso lendo
documentação. Os dados já sincronizados sugerem que a resposta não é óbvia: a maior
parte dos IDs nas faciais é baixa e sequencial (2, 3, 13, 22, 26, 38, 178, 192),
compatível com um `id`, mas há exceções muito maiores (494155, 856547) que parecem
outra numeração.

Isso se resolve com uma consulta real: de posse do token, uma chamada em uma conta
conhecida mostra se `id` ou `commonEnroll` bate com os IDs que já temos das faciais.
Enquanto isso não for verificado, não faz sentido escolher um dos dois no código.

## Fluxo proposto

1. O operador guarda, uma vez, o token e a conta do Sigma na interface.
2. Ele continua sincronizando as faciais como hoje, o que traz ID, nome e foto.
3. Um botão importa do Sigma e preenche apartamento e bloco de quem casar pelo
   identificador, sem tocar em nome nem foto.
4. A edição manual continua existindo, para quem não casar ou não estiver no Sigma.

O passo 3 preserva a divisão de posse já estabelecida no ADR 0007: o equipamento é
dono do nome e da foto, e o apartamento passa a ter o Sigma como origem, em vez do
preenchimento manual — que segue disponível.

## Riscos observados

- **Sobrescrever trabalho manual.** Um apartamento digitado à mão pode ser
  substituído por um valor errado do Sigma. Vale mostrar o que mudaria antes de
  aplicar, ou registrar de onde veio cada valor.
- **Uma pessoa em mais de uma unidade.** `unities` é uma lista. É preciso decidir o
  que fazer quando alguém aparece em duas unidades.
- **Contas por condomínio.** Cada condomínio é uma conta; com mais de um cliente, a
  conta precisa estar associada à facial, e não ao sistema todo.
