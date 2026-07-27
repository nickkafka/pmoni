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
