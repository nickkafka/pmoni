"""
Serving the built interface from the API.

During development Vite serves the interface and forwards the API calls here, so
both live at one address and every path in the interface can stay relative. The
packaged program has no Vite. Letting the window load the files straight from disk
would break exactly those paths — opened as `file://` a relative request has no host
to resolve against, and the WebSocket address built from `window.location.host`
comes out empty — so the API serves the interface instead and the address stays a
real one.
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.core.logger import logger
from app.core.paths import frontend_root

HASHED_ASSETS = "assets"
"""Onde o Vite põe o que tem o conteúdo no próprio nome."""

FOREVER = "public, max-age=31536000, immutable"
"""
Seguro justamente porque o nome carrega um resumo do conteúdo: mudou o arquivo,
mudou o nome, e o endereço antigo nunca mais é pedido.
"""

NEVER = "no-store"
"""
O `index.html` é o ponteiro para os nomes de agora. Guardado, ele continua apontando
para os de ontem — e a janela abre a versão anterior inteira, servida do cache, sem
chegar a perguntar nada ao backend. Foi o que aconteceu depois de uma atualização:
o programa era novo e a tela era velha.

O resto — fonte, logo, favicon — vem de `public/` e mantém o nome entre versões, o
que traz o mesmo problema. Relê tudo a cada abertura, o que custa milissegundos
vindo de um arquivo local.
"""


def mount_interface(app: FastAPI) -> None:
    """
    Hand the interface every path the API itself did not claim.

    Called after the routers are registered, because the first matching route wins
    and this one matches everything.
    """
    directory = frontend_root().resolve()
    index = directory / "index.html"

    if not index.is_file():
        logger.info(f"Interface não encontrada em {directory}. A API sobe sozinha.")
        return

    def served(path, *, hashed: bool) -> FileResponse:
        return FileResponse(path, headers={"Cache-Control": FOREVER if hashed else NEVER})

    @app.get("/{requested:path}", include_in_schema=False)
    async def interface(requested: str) -> FileResponse:
        candidate = (directory / requested).resolve()
        # Anything that is not a file we ship is a route of the interface, which
        # only the interface can resolve: the address bar may hold `/admin`, and
        # answering that with a 404 would break opening it directly.
        if candidate.is_file() and candidate.is_relative_to(directory):
            return served(candidate, hashed=candidate.parent.name == HASHED_ASSETS)
        return served(index, hashed=False)

    logger.info(f"Interface servida a partir de {directory}.")
