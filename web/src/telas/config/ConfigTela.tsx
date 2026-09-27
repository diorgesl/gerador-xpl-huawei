import { useEffect, useMemo, useState } from "react"
import { ChevronDown, Download } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CodigoXpl } from "@/components/CodigoXpl"
import { Falha } from "@/components/Falha"
import { useConfig, type SecaoConfig } from "@/api/consultas"
import { plural } from "@/lib/diff"
import { baixar, copiarComAviso } from "@/lib/copiar"
import { cn } from "@/lib/utils"
import { LINHA_DE_LEITURA, secaoNaLinha } from "./leitura"

/**
 * O texto do "copiar tudo": as secoes na ordem da tela, com uma linha em
 * branco entre elas. E o mesmo intervalo que separa os blocos dentro de uma
 * secao, e o que o operador esperaria de um arquivo unico.
 */
function textoInteiro(secoes: SecaoConfig[]) {
  return secoes.map((s) => s.texto).join("\n\n")
}

/**
 * As contagens do cabecalho. O tipo da secao sai do prefixo da chave, que e
 * o que o /api/config numera: "peer-", "grupo-", e o resto e base e
 * originacao.
 */
function contagem(secoes: SecaoConfig[]) {
  const quantos = (prefixo: string) =>
    secoes.filter((s) => s.chave.startsWith(prefixo)).length
  return {
    peers: quantos("peer-"),
    grupos: quantos("grupo-"),
    semArquivo: secoes.filter((s) => s.salvo === false).length,
  }
}

/**
 * A chave da secao que o operador esta lendo, para o sumario marcar onde ele
 * esta.
 *
 * Sao as medidas da rolagem, e nao um IntersectionObserver: com a faixa do
 * observador a marca fica uma secao atras enquanto a de cima ainda encosta na
 * janela, e no fim da pagina nao ha faixa nenhuma para onde ela ir. A decisao
 * de qual secao e a lida mora no leitura.ts, que tem teste; aqui fica so a
 * medida, que precisa de layout de verdade.
 */
function useSecaoNaTela(chaves: string[]) {
  const [atual, setAtual] = useState<string | null>(null)

  useEffect(() => {
    const medir = () => {
      const topos = chaves.map((chave) => {
        const secao = document.getElementById(chave)
        return secao ? secao.getBoundingClientRect().top : Infinity
      })
      const documento = document.documentElement
      const noFundo = window.scrollY + window.innerHeight >= documento.scrollHeight - 1
      setAtual(secaoNaLinha(chaves, topos, LINHA_DE_LEITURA, noFundo))
    }
    medir()
    // o resize entra junto: a janela mais baixa muda quantas secoes cabem
    window.addEventListener("scroll", medir, { passive: true })
    window.addEventListener("resize", medir)
    return () => {
      window.removeEventListener("scroll", medir)
      window.removeEventListener("resize", medir)
    }
  }, [chaves])

  return atual
}

export function ConfigTela() {
  const config = useConfig()
  // o `?? []` e um array novo a cada render: sem o memo ele mudaria a
  // identidade de `secoes` toda vez, e o efeito do observador seria desfeito e
  // refeito a toa, com as secoes ja na tela
  const secoes = useMemo(() => config.data?.secoes ?? [], [config.data])
  const chaves = useMemo(() => secoes.map((s) => s.chave), [secoes])
  const atual = useSecaoNaTela(chaves)

  // recolhidas, e nao abertas: a pagina abre com tudo a vista, que e o ponto
  // de conferir a config inteira, e o operador dobra o que ja leu
  const [recolhidas, setRecolhidas] = useState<ReadonlySet<string>>(new Set())
  const alternar = (chave: string) =>
    setRecolhidas((antes) => {
      const depois = new Set(antes)
      if (!depois.delete(chave)) depois.add(chave)
      return depois
    })

  // as mesmas duas razoes do BaseTela: o TanStack zera o `error` de uma
  // consulta sem dado quando ela e refeita, entao sem o `retentando` o aviso
  // sairia da tela no primeiro clique
  const tentando = config.isFetching
  const retentando = tentando && config.data === undefined && config.errorUpdateCount > 0
  const falhou = config.isError || retentando

  const conta = contagem(secoes)
  const texto = textoInteiro(secoes)

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <div>
        <h1 className="text-base font-semibold">Config completa</h1>
        <p className="text-xs text-muted-foreground">
          a config inteira, montada agora a partir do cadastro: o base, os
          grupos, os peers e a originação dos prefixos próprios, na ordem de
          colagem do README. O que ainda não está em{" "}
          <span className="dado">out/</span> vem marcado.
        </p>
      </div>

      {falhou && (
        <Falha
          mensagem="não deu para falar com a API"
          tentando={tentando}
          aoTentar={() => void config.refetch()}
        />
      )}

      {config.isLoading && <p className="text-sm text-muted-foreground">montando...</p>}

      {secoes.length > 0 && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => void copiarComAviso(texto)}>
              copiar tudo
            </Button>
            <Button size="sm" variant="ghost" onClick={() => baixar(texto, "config.txt")}>
              <Download className="size-4" /> baixar tudo
            </Button>
            <span className="ml-auto text-xs text-muted-foreground">
              {plural(conta.peers, "peer", "peers")},{" "}
              {plural(conta.grupos, "grupo", "grupos")},{" "}
              {conta.semArquivo} sem arquivo em out/
            </span>
            <Button size="sm" variant="ghost" onClick={() => setRecolhidas(new Set())}>
              expandir todas
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRecolhidas(new Set(chaves))}>
              recolher todas
            </Button>
          </div>

          {/* O sumario fica grudado no topo da janela: a pagina e longa por
              natureza, e sem ele achar uma secao e rolar no escuro.
              A altura e limitada, e o que passa rola dentro dele: sem o
              limite, uma lista de vinte peers viraria um bloco grudado de
              quatro linhas comendo a janela, e o `scroll-mt` da secao (que e
              um numero so) nao teria como acompanhar a altura */}
          <nav
            aria-label="Sumário das seções"
            className="sticky top-0 z-10 flex max-h-20 flex-wrap gap-1 overflow-y-auto rounded border bg-card p-2"
          >
            {secoes.map((s) => (
              <a
                key={s.chave}
                href={`#${s.chave}`}
                aria-current={atual === s.chave ? "true" : undefined}
                className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent aria-[current=true]:bg-accent aria-[current=true]:text-foreground"
              >
                {s.titulo}
              </a>
            ))}
          </nav>

          {secoes.map((s) => {
            const recolhida = recolhidas.has(s.chave)
            return (
              <section
                key={s.chave}
                id={s.chave}
                aria-labelledby={`${s.chave}-titulo`}
                // o scroll-mt deixa a secao abaixo do sumario grudado, e o
                // valor e maior que o `max-h-20` dele de proposito: sem ele o
                // salto do link para no topo da janela, que e onde o sumario
                // esta, e a secao chega escondida atras dele
                className="scroll-mt-24 rounded border bg-card"
              >
                <div className="flex flex-wrap items-center gap-2 p-2">
                  <h2 id={`${s.chave}-titulo`} className="min-w-0 flex-1">
                    <button
                      type="button"
                      aria-expanded={!recolhida}
                      aria-controls={`${s.chave}-corpo`}
                      onClick={() => alternar(s.chave)}
                      className="flex items-center gap-1 text-left text-sm font-semibold"
                    >
                      <ChevronDown
                        className={cn("size-4 shrink-0 transition-transform",
                                      recolhida && "-rotate-90")}
                      />
                      {s.titulo}
                    </button>
                  </h2>
                  {s.salvo === false && (
                    <Badge className="border-aviso-texto/30 bg-aviso-fundo text-aviso-texto"
                           variant="outline">
                      sem arquivo em out/
                    </Badge>
                  )}
                  {s.arquivo && (
                    <span className="dado text-xs text-muted-foreground">{s.arquivo}</span>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => void copiarComAviso(s.texto)}>
                    copiar
                  </Button>
                </div>
                {!recolhida && (
                  <div id={`${s.chave}-corpo`} className="px-2 pb-2">
                    <CodigoXpl texto={s.texto} />
                  </div>
                )}
              </section>
            )
          })}
        </>
      )}
    </div>
  )
}
