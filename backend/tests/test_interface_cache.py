"""
O que a janela pode guardar, e o que ela nunca pode.

Uma atualização já chegou a ficar invisível: o programa era novo, a tela era velha, e
o motivo era o `index.html` guardado no cache do Chromium apontando para os nomes de
arquivo da versão anterior. Como nada disso aparece em teste de tela, fica aqui.
"""

import unittest
import unittest.mock
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.interface import mount_interface


class InterfaceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "assets").mkdir()
        (root / "index.html").write_text("<html>pMoni</html>", encoding="utf-8")
        (root / "assets" / "index-AbC123.js").write_text("console.log(1)", encoding="utf-8")
        (root / "logo.png").write_bytes(b"\x89PNG")

        app = FastAPI()
        with unittest.mock.patch("app.api.interface.frontend_root", return_value=root):
            mount_interface(app)
        self.client = TestClient(app)

    def cache_of(self, path: str) -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.headers.get("cache-control", "")

    def test_never_stores_the_index(self) -> None:
        """É o ponteiro para os nomes de agora; guardado, aponta para os de ontem."""
        self.assertEqual(self.cache_of("/"), "no-store")

    def test_never_stores_an_interface_route_either(self) -> None:
        """`/admin` também devolve o index, e cair no cache tem o mesmo efeito."""
        self.assertEqual(self.cache_of("/admin"), "no-store")

    def test_keeps_a_hashed_asset_forever(self) -> None:
        """O conteúdo está no nome: mudou o arquivo, o endereço antigo não é pedido."""
        self.assertIn("immutable", self.cache_of("/assets/index-AbC123.js"))

    def test_does_not_keep_what_public_ships_under_a_fixed_name(self) -> None:
        """Logo e fontes mantêm o nome entre versões; guardados, congelam na antiga."""
        self.assertEqual(self.cache_of("/logo.png"), "no-store")


if __name__ == "__main__":
    unittest.main()
