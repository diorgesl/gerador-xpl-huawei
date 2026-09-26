"""O schema gerado tem que bater com o app.openapi().

Roda dentro da suite do Python de proposito: mudar app/api.py ou
app/modelos_api.py sem regerar web/src/api/schema.d.ts deixa o front
compilando contra um contrato velho. Sem o npm instalado (o caso do container,
que nao tem node_modules) o teste e pulado, e o check roda em quem tem o front.
"""

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"


@pytest.mark.skipif(not (WEB / "node_modules").is_dir(),
                    reason="front nao instalado: rode npm install em web/")
def test_o_schema_do_front_bate_com_o_openapi_do_app():
    resultado = subprocess.run(
        ["npm", "run", "--silent", "api:conferir"],
        cwd=WEB, capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
