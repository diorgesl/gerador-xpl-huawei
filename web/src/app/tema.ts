export type Tema = "claro" | "escuro" | "sistema"

const CHAVE = "tema"

/**
 * Ler e gravar o tema nunca pode derrubar a tela: em janela privada ou com o
 * storage bloqueado por politica, o localStorage lanca. A escolha vale so
 * nesta aba e a tela segue no tema do sistema.
 */
export function lerTema(): Tema {
  try {
    const guardado = localStorage.getItem(CHAVE)
    return guardado === "claro" || guardado === "escuro" ? guardado : "sistema"
  } catch {
    return "sistema"
  }
}

export function gravarTema(tema: Tema) {
  try {
    if (tema === "sistema") localStorage.removeItem(CHAVE)
    else localStorage.setItem(CHAVE, tema)
  } catch {
    // sem storage a escolha nao sobrevive ao recarregamento, e so
  }
}

export function aplicarTema(tema: Tema) {
  const escuro =
    tema === "escuro" ||
    (tema === "sistema" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", escuro)
}

// O estado do tema mora num contexto (web/src/app/provedores.tsx), e nao aqui:
// a paleta e as configuracoes trocam o tema por ele. Este modulo so tem a
// leitura, a gravacao e a aplicacao, que sao as partes testaveis.
