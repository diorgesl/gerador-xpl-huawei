import { toast } from "sonner"

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

/**
 * Copia e, quando nem o clipboard nem o execCommand funcionam, avisa que o
 * bloco ficou selecionado. As telas chamam esta, e nao a copiar direto: o
 * Ctrl+C manual e o unico caminho que sobra fora de origem segura.
 */
export async function copiarComAviso(texto: string, alvo?: HTMLElement | null) {
  const resultado = await copiar(texto, alvo)
  if (resultado === "selecionado") {
    toast("o bloco ficou selecionado: use Ctrl+C para copiar")
  }
  return resultado
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
  // as telas passam o painel inteiro, e o que interessa e o codigo dentro
  // dele: sem esta volta o Ctrl+C levaria junto o rotulo das abas e dos
  // botoes. O `code` e o bloco copiavel, com a numeracao de fora
  const elemento = alvo.querySelector("code") ?? alvo
  const selecao = document.getSelection()
  if (!selecao) return
  const intervalo = document.createRange()
  intervalo.selectNodeContents(elemento)
  selecao.removeAllRanges()
  selecao.addRange(intervalo)
}

/** O bloco como arquivo .txt, com o nome que ele tem em out/. */
export function baixar(texto: string, arquivo: string) {
  const blob = new Blob([texto], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = arquivo
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
