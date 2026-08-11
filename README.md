# pMoni

Sistema de monitoramento de acesso facial em tempo real.

Tecnologias:

- FastAPI
- Electron
- React
- SQLite

## Inicialização do backend

No diretório `backend`, instale as dependências:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

A aplicação sobe sem configuração nenhuma. Para ajustar o que muda por instalação —
senha da administração, porta — copie o modelo e edite:

```powershell
copy .env.example .env
```

As migrations são aplicadas na inicialização, então não é preciso rodar `alembic
upgrade head` à mão. O mesmo vale para a `DEVICE_CREDENTIALS_KEY`, que protege as
senhas dos equipamentos: se não houver uma no `.env`, a aplicação gera uma no
primeiro uso e guarda em `device-credentials.key`, ao lado do banco.

Essa chave pertence ao banco que ela cifrou. Restaurar um backup de um sem o outro
deixa as senhas ilegíveis e os equipamentos param de autenticar — os dois arquivos
viajam juntos.

Suba a API com:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

## Tela da portaria

No diretório `frontend`:

```powershell
npm install
npm run dev
```

A interface abre em `http://localhost:5173` e alcança a API pelo proxy do Vite. Se a
API estiver em outro endereço, informe `PMONI_API` antes de iniciar.

Para abrir a janela do Electron em vez do navegador, use `npm run electron`. Ela sobe
o backend já empacotado (`installer\build.ps1` precisa ter rodado antes), então serve
para conferir o programa como ele fica instalado, não para desenvolver a interface.

O terminal integrado do VS Code exporta `ELECTRON_RUN_AS_NODE=1`, herdado do próprio
editor. Com essa variável o Electron roda o script como Node puro e o `require`
devolve um caminho em vez da API, o que quebra na primeira linha. Rode `npm run
electron` num terminal de fora do editor, ou limpe a variável antes.

## Consulta de morador na portaria

Quando a facial não reconhece alguém, o porteiro procura pela pessoa no campo do
cabeçalho — por nome, documento ou apartamento, tudo no mesmo campo. Basta começar a
digitar: qualquer tecla na tela vazia cai na busca, e `Esc` fecha.

A busca aceita o que se digita às pressas. "joao" acha "João", o documento é achado
com ou sem pontuação, e quem está cadastrado em várias faciais aparece uma vez só,
reunindo o que foi informado em qualquer um dos cadastros.

**Apartamento e bloco se procuram com um traço na frente**: `-301` acha o apartamento
301, `-A` acha o bloco A. O traço existe porque muitos apartamentos são só um número:
digitado solto, `1` é curto demais para valer uma busca, e `12` alcançaria qualquer
documento que contenha esses dígitos. O traço diz de qual campo se trata, o que torna
um único caractere suficiente e mantém a resposta nos apartamentos. Um "i" ao lado do
campo explica isso na tela.

Os resultados abrem uma coluna ao lado, e não uma janela por cima: a portaria existe
para mostrar quem está passando, e as passagens continuam chegando enquanto o
porteiro procura. A passagem atual apenas estreita e segue visível.

Apartamento e documento virão da integração com o Sigma, ainda pendente de liberação
de permissão. Enquanto isso, os dois podem ser digitados em **Administração →
Moradores**, o que já permite usar e testar a busca. O ponto de entrada dos dados do
Sigma está pronto e documentado em [docs/sigma-cloud-api.md](docs/sigma-cloud-api.md);
ele grava pela mesma porta que a edição manual.

Apartamento, bloco e documento pertencem à pessoa, não ao cadastro de um equipamento:
informá-los grava em todas as faciais em que ela está, para que a resposta seja a
mesma em qualquer portaria.

## Acesso à administração

A tela da portaria é aberta: a guarita precisa subir sozinha, sem ninguém para
digitar uma senha. Já a administração exige login, e as rotas administrativas da
API recusam quem não fez login — bloquear apenas a tela não protegeria nada.

O padrão é `prever` / `prever`. Para trocar, defina no `.env` do backend:

```
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
ADMIN_SESSION_MINUTES=30
```

A sessão vive apenas na memória: reiniciar a aplicação, ou recarregar a página,
pede a senha de novo.

## Exportar e importar as faciais

Em **Administração → Equipamentos**, os botões **Exportar** e **Importar** levam a
configuração dos equipamentos para um arquivo JSON e de volta. O "i" ao lado mostra
o formato, para quem preferir escrever o arquivo à mão.

**A exportação não inclui as senhas**, e isso é deliberado: as senhas das faciais são
guardadas cifradas com uma chave que nunca é versionada, e um arquivo na pasta de
downloads com a senha de cada portaria desfaria essa proteção inteira.

Nada disso obriga ninguém a abrir o JSON. **A senha pode faltar no arquivo**: os
equipamentos novos que vierem sem ela são listados num pop-up logo após a importação,
para você digitar todas de uma vez e cadastrá-los. Eles só entram depois disso —
cadastrar um equipamento sem credencial deixaria o supervisor tentando alcançá-lo e
falhando a cada ciclo, sem nada na tela explicando por quê.

Um equipamento que já existe no mesmo endereço e porta é **atualizado, não
duplicado**, e sem `password` a senha guardada é mantida. Por isso o arquivo
exportado pode ser reimportado como está.

## Importação automática

Quem é cadastrado numa facial durante o dia só aparecia no pMoni quando alguém
lembrava de apertar sincronizar — e o porteiro que procurasse essa pessoa não a
encontrava. Em **Administração → Importação automática** define-se um horário, e a
rotina passa a importar os cadastros de todas as faciais habilitadas todo dia.

O painel mostra quando foi a última importação e como ela terminou. São três
desfechos, e a diferença entre eles importa:

| Estado | O que significa |
| --- | --- |
| Concluída | Todas as faciais responderam. |
| Concluída com falhas | Importou, mas uma facial não respondeu — quem só está cadastrado nela ficou de fora. |
| Falhou | Nenhuma respondeu, ou não há equipamento habilitado. |

Mudar o horário vale na hora, sem reiniciar. A rotina roda no horário local da
máquina da portaria.

Uma limitação a conhecer: o agendamento vive na memória do processo. Se a máquina
estiver desligada na hora marcada, aquele dia é pulado — a importação não é
recuperada ao ligar. Numa guarita que fica ligada direto isso não aparece, mas vale
saber antes de escolher um horário em que a máquina costuma estar fora do ar.

A importação do Sigma entrará nessa mesma rotina, depois das faciais, quando a
permissão for liberada — ela preenche apartamento e documento de quem as faciais
acabaram de trazer.

## Gerando o instalador

Para distribuir o pMoni a um computador que não tem Python nem Node instalados:

```powershell
.\installer\build.ps1
```

O resultado é `frontend\release\pMoni Setup 0.1.0.exe`, um instalador que não pede
direitos de administrador. Ele instala por usuário, cria o atalho e é a única coisa
que precisa ser copiada para a máquina de destino.

O script encadeia três etapas, e a ordem entre elas não é opcional: o Vite constrói
a interface, o PyInstaller embute essa interface junto do backend num executável, e o
electron-builder embute esse executável no instalador. Rodar uma etapa isolada
depois de mexer no código de outra gera um instalador com uma versão antiga dentro.

Repetindo o build na mesma máquina, `.\installer\build.ps1 -SkipInstall` pula a
reinstalação das dependências.

O empacotamento em si acontece em `%LOCALAPPDATA%\pMoni-build`, e só o instalador
pronto é copiado para `frontend\release`. O motivo é o OneDrive: este projeto vive
numa pasta sincronizada, e o electron-builder precisa renomear um diretório de
~500 MB durante o empacotamento — dentro da árvore do OneDrive esse rename volta
"acesso negado", mesmo com o aplicativo fechado, porque o filtro de arquivos dele
segue ativo. Copiar o `.exe` pronto de volta é escrita comum e passa sem problema.

O instalador sai com o ícone padrão do Electron. Para trocar, coloque um `.ico` de
256×256 em `frontend/build/icon.ico`, que é onde o electron-builder procura.

## Como o programa instalado se organiza

A janela do Electron não desenha a interface: ela sobe o backend como processo
filho, espera o `/health` responder e abre `http://127.0.0.1:8000`. O caminho mais
curto seria carregar os arquivos direto do disco, mas a interface acessa a API por
caminhos relativos e monta o endereço do WebSocket a partir de
`window.location.host` — sob `file://` não há host, e nada disso resolveria. Servir
pelo próprio backend mantém em produção o mesmo endereço único que o proxy do Vite
dá em desenvolvimento.

Se a porta 8000 estiver ocupada, o Electron escolhe outra livre em vez de falhar.

O programa fica em `%LOCALAPPDATA%\Programs\pMoni` e é somente leitura. Tudo o que
a instalação acumula fica separado, em `%LOCALAPPDATA%\pMoni`:

| Arquivo | O que é |
| --- | --- |
| `pmoni.db` | O banco. |
| `device-credentials.key` | A chave que cifra as senhas dos equipamentos. |
| `logs\pmoni.log` | O log, com rotação a cada 10 MB. |
| `.env` | Opcional, para trocar senha do administrativo ou porta. |

Desinstalar não apaga essa pasta, e é dela que sai o backup.

## Primeiro uso

1. Cadastre o equipamento em `POST /devices` (aceita endereço IP ou nome DDNS).
2. Sincronize as pessoas com `POST /residents/sync/{device_id}`, que copia nome e foto
   do cadastro biométrico.
3. Informe o apartamento de cada morador com `PATCH /residents/{employee_no}`. Esse dado
   não existe no equipamento e passará a vir do Sigma em uma etapa futura.
