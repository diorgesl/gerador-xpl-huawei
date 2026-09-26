// O que vai para o equipamento tem que ser o que esta em out/. Fora de origem
// segura (o app aberto por HTTP de outra maquina) o navegador nao expoe o
// navigator.clipboard, e a copia crua derrubava o botao inteiro: por isso os
// dois degraus abaixo, e o ultimo pede o Ctrl+C ao operador.
export type ResultadoCopia = "copiado" | "selecionado"

export async function copiar(texto: string, alvo?: HTMLElement | null): Promise<ResultadoCopia> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(texto)
      return "copiado"
    }
  } catch {
    // sem permissao ou fora de origem segura: o proximo degrau resolve
  }
  if (porSelecao(texto)) return "copiado"
  selecionar(alvo)
  return "selecionado"
}

function porSelecao(texto: string): boolean {
  const area = document.createElement("textarea")
  area.value = texto
  area.setAttribute("readonly", "")
  area.style.position = "fixed"
  area.style.top = "-1000px"
  document.body.appendChild(area)
  try {
    area.select()
    return document.execCommand("copy")
  } catch {
    return false
  } finally {
    area.remove()
  }
}

function selecionar(alvo?: HTMLElement | null) {
  if (!alvo) return
  const selecao = document.getSelection()
  if (!selecao) return
  const intervalo = document.createRange()
  intervalo.selectNodeContents(alvo)
  selecao.removeAllRanges()
  selecao.addRange(intervalo)
}
