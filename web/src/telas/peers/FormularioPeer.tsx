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

  // Number("") e 0, e o id 0 e um id como os outros: sem esta guarda o
  // formulario novo (id vazio) se veria como o peer de id 0, o esconderia da
  // lista de origens e acharia que ele reaproveita deste formulario
  const id = String(valores.id ?? "")

  // As origens que o par tipo/ASN aceita, com a opcao vazia no topo. Quem cede
  // politica e dono dela: nao pode reaproveitar de outro nem estar num grupo,
  // porque nos dois casos o bloco dele nao define os filtros que quem
  // reaproveita iria chamar. A opcao vazia e o estado de quem carrega a
  // propria politica, como o "— sem grupo —" do grupo_id: sem ela o
  // reaproveitamento seria porta de mao unica na tela, e voltar atras so
  // sairia pela API
  const origensDoPar = (tipo: string, asn: string): Opcao[] => [
    { valor: "", rotulo: "— carrega a própria política —" },
    ...peers
      .filter((p) => (id === "" || p.id !== Number(id))
        && p.tipo === tipo
        && p.asn === Number(asn)
        && p.politica_de == null
        && p.grupo_id == null)
      .map((p) => ({ valor: String(p.id), rotulo: p.apelido || p.nome || p.token })),
  ]

  const origens = origensDoPar(String(valores.tipo ?? ""), String(valores.asn ?? ""))

  // o vazio nao e uma origem: sem a guarda a nota diria "a politica vem do
  // peer — carrega a propria politica —"
  const escolhida = origens.find((o) => o.valor !== "" && o.valor === String(valores.politica_de))
  const notaDaPolitica = escolhida
    ? `A política vem do peer ${escolhida.rotulo}. Editar estes campos não muda o que é gerado.`
    : undefined

  /**
   * A escolha de origem vale no par tipo/ASN, e trocar o par a limpa: a lista
   * e outra, e o id velho ficaria como uma opcao fora da lista (um numero solto
   * no gatilho) ate o salvar recusar. Quem chama e a edicao do operador, pelo
   * `por` do Formulario: o reset do registro salvo e a copia escrevem no
   * formulario por fora dele, e nao podem apagar a escolha que veio gravada.
   */
  function aoEditarCampo(campo: string, valor: unknown) {
    if (campo !== "tipo" && campo !== "asn") return
    const atual = String(valores.politica_de ?? "")
    if (atual === "") return
    const tipo = campo === "tipo" ? String(valor ?? "") : String(valores.tipo ?? "")
    const asn = campo === "asn" ? String(valor ?? "") : String(valores.asn ?? "")
    if (origensDoPar(tipo, asn).some((o) => o.valor === atual)) return
    form.setValue("politica_de", "", { shouldDirty: true })
  }

  // quem cede politica carrega o token que nomeia os filtros que o outro
  // chama: renomear o apelido daqui muda o nome dos objetos do bloco de la,
  // que fica desatualizado ate ser gerado de novo
  const dependentes = peers.filter((p) => id !== "" && p.politica_de === Number(id))
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
      aoEditarCampo={aoEditarCampo}
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
