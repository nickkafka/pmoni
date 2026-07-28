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
deles informando a empresa. Ou seja, o Monikraft apenas guarda e usa um token que
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

E `BlockUnitDTO` traz exatamente os dois campos que faltavam no Monikraft:

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

## A questão em aberto que decide a viabilidade

**Qual campo do Sigma corresponde ao ID que a facial informa no evento?**

O Monikraft casa o evento com o cadastro pelo `employeeNo` da facial. Para preencher
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
