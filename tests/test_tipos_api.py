"""O schema gerado tem que bater com o app.openapi().

Roda dentro da suite do Python de proposito: mudar app/api.py ou
app/modelos_api.py sem regerar web/src/api/schema.d.ts deixa o front
compilando contra um contrato velho.

O check precisa das duas coisas: o node_modules do front e o npm no PATH. Nao
basta olhar o node_modules: o compose.yaml monta o checkout em /app, entao
dentro do container o node_modules da maquina aparece, mas a imagem
python:3.14-slim nao tem npm e o subprocess.run estoura com FileNotFoundError.
A condicao do skip e o par, e o container e pulado pelo mesmo motivo de quem
nunca rodou npm install.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"


@pytest.mark.skipif(not (WEB / "node_modules").is_dir() or shutil.which("npm") is None,
                    reason="front nao instalado ou npm fora do PATH: rode npm install em web/")
def test_o_schema_do_front_bate_com_o_openapi_do_app():
    resultado = subprocess.run(
        ["npm", "run", "--silent", "api:conferir"],
        cwd=WEB, capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
