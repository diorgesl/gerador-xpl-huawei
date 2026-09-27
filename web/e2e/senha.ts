/**
 * A senha que o bootstrap do e2e cria.
 *
 * A arvore de web/e2e/.tmp nasce vazia a cada rodada, entao o usuarios.yaml
 * do e2e e sempre novo e este e o admin dele. A constante mora aqui para que
 * a config, que a poe no ambiente do uvicorn, e o setup, que a digita na
 * tela, nao possam divergir.
 */
export const SENHA = "senha-do-e2e"
