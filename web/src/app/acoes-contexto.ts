import { createContext, useContext, useEffect, useMemo, useRef } from "react"

/** O que a tela aberta sabe fazer, para a paleta e o Ctrl+S alcancarem. */
export type AcoesDaTela = {
  aoSalvar?: () => void
  aoDuplicar?: () => void
  aoCopiarBloco?: () => void
}

const CAMPOS = ["aoSalvar", "aoDuplicar", "aoCopiarBloco"] as const

// Um contexto so, o de escrita: a tela publica as acoes dela e a casca guarda o
// que recebeu e passa para a paleta por prop. Um contexto de leitura existiria
// para a paleta ler, mas ela nao esta dentro do provedor (renderiza fora do
// main), entao seria superficie morta.
export const ContextoDefinirAcoes = createContext<(a: AcoesDaTela) => void>(() => {})

export function useDefinirAcoes() {
  return useContext(ContextoDefinirAcoes)
}

/**
 * Publica as acoes da tela aberta com um objeto ESTAVEL, cujos campos chamam um
 * ref atualizado a cada render. O caminho ingenuo, que e publicar dentro de um
 * efeito que depende dos handlers, vira laco: handler novo a cada render, entao
 * objeto novo publicado, entao re-render, entao handler novo. As telas chamam
 * isto uma vez e nao precisam memoizar nada.
 */
export function usePublicarAcoes(acoes: AcoesDaTela) {
  const atual = useRef(acoes)
  const definir = useDefinirAcoes()

  // O ref e atualizado depois do render, e nao durante: escrever nele no corpo
  // do componente e erro pela regra `react-hooks/refs` do plugin de hooks.
  // Como o efeito roda a cada render, o ref esta sempre com as acoes do ultimo
  // render que commitou, que e o que um clique le.
  useEffect(() => {
    atual.current = acoes
  })

  // A presenca dos campos, como chave: so muda quando a tela passa a declarar
  // (ou deixa de declarar) uma acao. Quem decide a presenca e a `acoes` do
  // render, e nao o ref: ler o ref durante o render e erro da mesma regra que
  // tirou a escrita dele dali. A chave tambem da a identidade do objeto
  // publicado: o memo reassina quando ela muda, e so quando ela muda.
  const chave = CAMPOS.filter((campo) => Boolean(acoes[campo])).join(" ")

  // O objeto publicado so tem os campos que a tela declarou, e nao os tres
  // sempre. A paleta decide mostrar "duplicar" e "copiar o bloco" pela PRESENCA
  // deles: com os tres sempre presentes, a paleta ofereceria duas acoes mortas
  // em toda tela, e clicar nelas nao faria nada.
  //
  // Quem decide que o Ctrl+S e do app, mesmo numa tela sem o que salvar, e o
  // atalho, e nao esta forma: ele sempre dispensa o padrao do navegador.
  const estavel = useMemo<AcoesDaTela>(() => {
    const saida: AcoesDaTela = {}
    for (const campo of CAMPOS) {
      if (chave.includes(campo)) saida[campo] = () => atual.current[campo]?.()
    }
    return saida
  }, [chave])

  // Ao sair da tela as acoes dela saem junto. Sem a limpeza, a paleta continua
  // oferecendo o que a tela que saiu sabia fazer, e o Ctrl+S chama um handler
  // fechado sobre estado que nao existe mais.
  useEffect(() => {
    definir(estavel)
    return () => definir({})
  }, [definir, estavel])
}
