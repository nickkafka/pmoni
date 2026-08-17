from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    """Sinal de vida, usado pelo Electron para saber quando abrir a janela.

    Nome e versão saem das configurações, e não escritos aqui: repetidos, iam
    divergir na primeira vez que a versão subisse — e esta rota é justamente onde
    alguém olha para saber o que está rodando.
    """
    return {
        "status": "online",
        "application": settings.APP_NAME,
        "version": settings.VERSION,
    }
