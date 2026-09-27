import type { UseFormReturn } from "react-hook-form"
import { Formulario } from "@/components/Formulario"
import { CAMPOS_POR_TIPO_GRUPO, CASCATA_GRUPO, SECOES_GRUPO } from "@/lib/campos"
import type { GrupoForm, Plano } from "@/api/consultas"
import { acoesDePrefixo } from "@/telas/peers/FormularioPeer"
import { CAMPOS_GRUPO } from "./camposGrupo"

export function FormularioGrupo({ form, plano, erros, avisos, erroIrr, aoIrPara, aoConsultarIrr }: {
  form: UseFormReturn<GrupoForm>
  plano: Plano
  erros: Record<string, string>
  avisos: { campo: string; mensagem: string }[]
  erroIrr?: string | null
  aoIrPara: (campo: string | null, secao: string | null) => void
  aoConsultarIrr?: (forcar: boolean) => void
}) {
  // O mapa vazio vale como ausente, como no FormularioPeer: um
  // `campos_por_tipo_grupo: {}` da API faria toda a visibilidade e a nota
  // pararem de valer sem avisar
  const camposPorTipo = Object.keys(plano.campos_por_tipo_grupo ?? {}).length > 0
    ? plano.campos_por_tipo_grupo
    : CAMPOS_POR_TIPO_GRUPO

  return (
    <Formulario
      form={form}
      campos={CAMPOS_GRUPO}
      secoes={SECOES_GRUPO}
      camposPorTipo={camposPorTipo}
      cascataCampos={CASCATA_GRUPO}
      plano={plano}
      grupos={[]}
      erros={erros}
      avisos={avisos}
      deGrupo
      aoIrPara={aoIrPara}
      acaoDaSecao={(secao) =>
        secao.id === "prefixos" && aoConsultarIrr
          ? acoesDePrefixo(erroIrr ?? null, aoConsultarIrr)
          : null
      }
    />
  )
}
