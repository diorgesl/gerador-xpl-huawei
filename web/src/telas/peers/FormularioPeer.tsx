import type { UseFormReturn } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Formulario } from "@/components/Formulario"
import { CAMPOS_POR_TIPO, CASCATA_PEER, SECOES_PEER } from "@/lib/campos"
import type { Opcao } from "./camposPeer"
import type { PeerForm, Plano } from "@/api/consultas"
import { CAMPOS_PEER } from "./camposPeer"

/** Os botoes do IRR moram na secao de prefixos, e nao no corpo do formulario. */
export function acoesDePrefixo(erro: string | null, aoConsultar: (forcar: boolean) => void) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <Button type="button" size="sm" variant="ghost" onClick={() => aoConsultar(false)}>
        consultar IRR
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => aoConsultar(true)}>
        consultar ignorando o cache
      </Button>
      {erro && <p role="alert" className="text-xs text-erro-texto">{erro}</p>}
    </div>
  )
}

export function FormularioPeer({ form, plano, grupos, erros, avisos, erroIrr, aoIrPara, aoConsultarIrr }: {
  form: UseFormReturn<PeerForm>
  plano: Plano
  grupos: Opcao[]
  erros: Record<string, string>
  avisos: { campo: string; mensagem: string }[]
  erroIrr?: string | null
  aoIrPara: (campo: string | null, secao: string | null) => void
  aoConsultarIrr?: (forcar: boolean) => void
}) {
  // O mapa vazio vale como ausente: com `??` so, um `campos_por_tipo: {}` da
  // API cairia como verdadeiro, o `pertenceAoTipo` responderia true para os
  // quinze campos com tipo, e toda a regra de visibilidade e a nota parariam
  // de valer em silencio
  const camposPorTipo = Object.keys(plano.campos_por_tipo ?? {}).length > 0
    ? plano.campos_por_tipo
    : CAMPOS_POR_TIPO

  return (
    <Formulario
      form={form}
      campos={CAMPOS_PEER}
      secoes={SECOES_PEER}
      camposPorTipo={camposPorTipo}
      cascataCampos={CASCATA_PEER}
      plano={plano}
      grupos={grupos}
      erros={erros}
      avisos={avisos}
      aoIrPara={aoIrPara}
      acaoDaSecao={(secao) =>
        secao.id === "prefixos" && aoConsultarIrr
          ? acoesDePrefixo(erroIrr ?? null, aoConsultarIrr)
          : null
      }
    />
  )
}
