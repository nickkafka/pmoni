# Monikraft

Sistema de monitoramento de acesso facial em tempo real.

Tecnologias:

- FastAPI
- Electron
- React
- SQLite

## Inicialização do backend

No diretório `backend`, instale as dependências e aplique o schema antes de iniciar a API:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Para habilitar o cadastro de dispositivos, defina `DEVICE_CREDENTIALS_KEY` com uma chave Fernet. Ela pode ser gerada com `Fernet.generate_key()` e não deve ser versionada.

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
API estiver em outro endereço, informe `MONIKRAFT_API` antes de iniciar.

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

## Primeiro uso

1. Cadastre o equipamento em `POST /devices` (aceita endereço IP ou nome DDNS).
2. Sincronize as pessoas com `POST /residents/sync/{device_id}`, que copia nome e foto
   do cadastro biométrico.
3. Informe o apartamento de cada morador com `PATCH /residents/{employee_no}`. Esse dado
   não existe no equipamento e passará a vir do Sigma em uma etapa futura.
