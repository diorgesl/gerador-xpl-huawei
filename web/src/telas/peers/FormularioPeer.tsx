import { useWatch, type UseFormReturn } from "react-hook-form"
import { Button } from "@/components/ui/button"
import { Formulario } from "@/components/Formulario"
import { CAMPOS_POR_TIPO, CASCATA_PEER, SECOES_PEER } from "@/lib/campos"
import type { Opcao } from "./camposPeer"
import type { PeerForm, PeerResumo, Plano } from "@/api/consultas"
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

export function FormularioPeer({ form, plano, grupos, peers, erros, avisos, erroIrr, aoIrPara, aoConsultarIrr }: {
  form: UseFormReturn<PeerForm>
  plano: Plano
  grupos: Opcao[]
  peers: PeerResumo[]
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

  // O retrato do render: a lista de origens depende do tipo e do ASN que o
  // formulario tem AGORA, e quem os tem e o formulario
  const valores = useWatch({ control: form.control }) as unknown as PeerForm

  // Quem cede politica e dono dela: nao pode reaproveitar de outro nem estar
  // num grupo, porque nos dois casos o bloco dele nao define os filtros que
  // quem reaproveita iria chamar.
  const origens = peers
    .filter((p) => p.id !== Number(valores.id)
      && p.tipo === valores.tipo
      && p.asn === Number(valores.asn)
      && p.politica_de == null
      && p.grupo_id == null)
    .map((p) => ({ valor: String(p.id), rotulo: p.apelido || p.nome || p.token }))

  const escolhida = origens.find((o) => o.valor === String(valores.politica_de))
  const notaDaPolitica = escolhida
    ? `A política vem do peer ${escolhida.rotulo}. Editar estes campos não muda o que é gerado.`
    : undefined

  // quem cede politica carrega o token que nomeia os filtros que o outro
  // chama: renomear o apelido daqui muda o nome dos objetos do bloco de la,
  // que fica desatualizado ate ser gerado de novo
  const dependentes = peers.filter((p) => p.politica_de === Number(valores.id))
  const avisoDoToken = dependentes.length === 0
    ? undefined
    : `${dependentes.length === 1
        ? "Um peer reaproveita"
        : `${dependentes.length} peers reaproveitam`} a política deste. Mudar o apelido troca o token, e com ele o nome dos filtros que ele chama.`

  return (
    <Formulario
      form={form}
      campos={CAMPOS_PEER}
      secoes={SECOES_PEER}
      camposPorTipo={camposPorTipo}
      cascataCampos={CASCATA_PEER}
      plano={plano}
      grupos={grupos}
      origens={origens}
      notaDaPolitica={notaDaPolitica}
      avisoDoToken={avisoDoToken}
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
