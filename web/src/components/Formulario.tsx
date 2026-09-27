import type { ReactNode } from "react"
import { useWatch, type FieldValues, type Path, type UseFormReturn } from "react-hook-form"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Campo } from "@/components/Campo"
import { CampoCombo } from "@/components/CampoCombo"
import { ResumoErros } from "@/components/ResumoErros"
import { cascata, erroDoCampo, pertenceAoTipo, secoesComErro, visivel } from "@/lib/campos"
import type { Secao, Valores } from "@/lib/campos"
// o `Campo` do componentes/Campo.tsx e o `Campo` da tabela de campos tem o
// mesmo nome, e os dois entram neste arquivo: a tabela fica com o apelido
// `CampoTabela` aqui dentro, e os dois modulos seguem exportando `Campo`
import type { Campo as CampoTabela, Contexto, Opcao } from "@/telas/peers/camposPeer"
import type { Plano } from "@/api/consultas"

export type Aviso = { campo: string; mensagem: string }

type Props<T extends FieldValues> = {
  form: UseFormReturn<T>
  campos: CampoTabela[]
  secoes: Secao[]
  camposPorTipo: Record<string, string[]>
  cascataCampos: string[]
  plano: Plano
  grupos: Opcao[]
  erros: Record<string, string>
  avisos: Aviso[]
  deGrupo?: boolean
  aoIrPara: (campo: string | null, secao: string | null) => void
  aoTrocarClasse?: (classe: string) => void
  // A secao de prefixos tem os botoes de consultar o IRR, que sao acao da tela
  // e nao do formulario: quem desenha a secao e o Formulario, e quem sabe o que
  // fazer com o resultado e a tela
  acaoDaSecao?: (secao: Secao) => ReactNode
}

export function Formulario<T extends FieldValues>({
  form, campos, secoes, camposPorTipo, cascataCampos, plano, grupos, erros, avisos,
  deGrupo = false, aoIrPara, acaoDaSecao,
}: Props<T>) {
  // o retrato deste render: a cascata le o formulario daqui, e o `visivel` sai
  // do mesmo lugar. O `as` e porque o useWatch devolve o formulario inteiro
  // sem tipo, e o Valores e a forma que o campos.ts entende
  const valores = useWatch({ control: form.control }) as unknown as Valores
  const tipo = String(valores.tipo ?? "cliente")
  const contagem = secoesComErro(erros, tipo, deGrupo, secoes)
  const ctx: Contexto = { plano, tipo, grupos }

  const por = (nome: string, valor: unknown) =>
    form.setValue(nome as Path<T>, valor as never, { shouldDirty: true })

  // A cascata roda aqui: o select do tipo nao sabe o que fazer com o resto do
  // modelo, e o campo que ainda esta no default do tipo anterior e o unico que
  // se move.
  function aoTrocarTipo(novo: string) {
    const novos = cascata(tipo, novo, valores, plano.padroes, cascataCampos, String(valores.classe ?? ""))
    por("tipo", novo)
    for (const [nome, valor] of Object.entries(novos)) {
      if (nome !== "tipo" && nome !== "classe") por(nome, valor)
    }
  }

  function aoTrocarClasse(nova: string) {
    // O `valores` do `useWatch` e o retrato deste render, entao a classe nova
    // ainda nao esta nele. A cascata le a classe de dentro do objeto para
    // comparar com a anterior, e sem a troca aqui a comparacao seria "a classe
    // mudou?" com o mesmo valor dos dois lados, que nunca e verdade: a origem
    // do downstream ficaria presa na comunidade da classe anterior
    const classeAntes = String(valores.classe ?? "")
    const novos = cascata(tipo, tipo, { ...valores, classe: nova }, plano.padroes, [], classeAntes)
    for (const [nome, valor] of Object.entries(novos)) {
      if (nome !== "classe" && nome !== "tipo") por(nome, valor)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ResumoErros erros={erros} tipo={tipo} deGrupo={deGrupo} aoIrPara={aoIrPara} />

      <nav aria-label="Seções do formulário" className="flex flex-wrap gap-2 text-xs">
        {secoes.map((s) => (
          <a key={s.id} href={`#secao-${s.id}`} className="rounded border px-2 py-0.5 hover:bg-accent">
            {/* o espaco entre as duas expressoes tem que estar escrito, e na
                mesma linha: o JSX come o texto que so tem espaco e quebra de
                linha, e o nome acessivel sairia "Identificação(1)" */}
            {s.rotulo} {contagem[s.id] > 0 && <span className="text-erro-texto">({contagem[s.id]})</span>}
          </a>
        ))}
      </nav>

      {secoes.map((secao) => {
        const visiveis = campos.filter(
          (c) => c.secao === secao.id && visivel(c.nome, valores, erros, camposPorTipo, tipo, deGrupo),
        )
        if (visiveis.length === 0) return null
        return (
          <fieldset key={secao.id} id={`secao-${secao.id}`} className="rounded border p-3">
            <legend className="px-1 text-[11px] uppercase tracking-wide text-muted-foreground">
              {secao.rotulo}
            </legend>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {visiveis.map((campo) => (
                <CampoRender
                  key={campo.nome}
                  campo={campo}
                  ctx={ctx}
                  bruto={valores[campo.nome]}
                  erro={erroDoCampo(campo.nome, erros, tipo, deGrupo)}
                  aviso={avisos.find((a) => a.campo === campo.nome)?.mensagem}
                  nota={pertenceAoTipo(campo.nome, camposPorTipo, tipo)
                    ? undefined
                    : `o bloco de ${tipo} não usa este campo`}
                  aoMudar={por}
                  aoTrocarTipo={aoTrocarTipo}
                  aoTrocarClasse={aoTrocarClasse}
                />
              ))}
            </div>
            {acaoDaSecao?.(secao)}
          </fieldset>
        )
      })}
    </div>
  )
}

function linhasDe(valor: unknown): string[] {
  return Array.isArray(valor) ? (valor as string[]) : []
}

function CampoRender({ campo, ctx, bruto, erro, aviso, nota, aoMudar, aoTrocarTipo, aoTrocarClasse }: {
  campo: CampoTabela
  ctx: Contexto
  bruto: unknown
  erro?: string
  aviso?: string
  nota?: string
  aoMudar: (nome: string, valor: unknown) => void
  aoTrocarTipo: (tipo: string) => void
  aoTrocarClasse: (classe: string) => void
}) {
  const id = campo.nome
  const base = campo.opcoes?.(ctx) ?? []
  // Um valor guardado que nao esta na lista (origem fora da tabela do tipo, LP
  // digitado a mao) entra como opcao dele mesmo: sem isso o select abriria no
  // vazio e o operador salvaria por cima sem ver o que havia
  const opcoes: Opcao[] =
    bruto && !base.some((o) => o.valor === String(bruto))
      ? [{ valor: String(bruto), rotulo: `${bruto}${campo.rotuloForaDaLista ?? ""}` }, ...base]
      : base
  const placeholder = typeof campo.placeholder === "function" ? campo.placeholder(ctx) : campo.placeholder

  // a contagem de linhas da lista vai no rotulo: e o que diz ao operador
  // quantos prefixos aquela caixa tem sem ele contar linha por linha
  const rotulo = campo.tipo === "area" ? `${campo.rotulo} (${linhasDe(bruto).length})` : campo.rotulo

  const controle = () => {
    switch (campo.tipo) {
      case "caixa":
        return <Checkbox id={id} checked={Boolean(bruto)} onCheckedChange={(v) => aoMudar(id, Boolean(v))} />
      case "select":
        return (
          <Select
            value={String(bruto ?? "")}
            onValueChange={(v) => {
              // o onValueChange do Base UI entrega `string | null`, e o modelo
              // do formulario so tem string: o nulo vira o vazio, que e o
              // mesmo que o `value` deste select ja escreve em `bruto ?? ""`
              const valor = v ?? ""
              aoMudar(id, valor)
              if (id === "tipo") aoTrocarTipo(valor)
              else if (id === "classe") aoTrocarClasse(valor)
            }}
          >
            <SelectTrigger id={id}>
              {/* Medido: o Value do Base UI mostra o VALOR cru quando nao
                  recebe funcao, entao a tabela de campos gastaria o rotulo
                  ("1100 - cliente de transito") para o operador ler "1100".
                  O rotulo da opcao escolhida sai daqui */}
              <SelectValue>
                {(v) => opcoes.find((o) => o.valor === String(v ?? ""))?.rotulo || placeholder || "—"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {opcoes.map((o) => (
                <SelectItem key={o.valor} value={o.valor}>{o.rotulo}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )
      case "combo":
        return (
          <CampoCombo nome={id} valor={String(bruto ?? "")} opcoes={opcoes} mono={campo.mono}
            placeholder={placeholder} aoMudar={(v) => aoMudar(id, v)} />
        )
      case "area":
        return (
          <Textarea
            id={id}
            rows={campo.linhas ?? 3}
            spellCheck={false}
            className={campo.mono ? "dado" : undefined}
            value={linhasDe(bruto).join("\n")}
            onChange={(e) => aoMudar(id, e.target.value.split("\n").filter((l) => l.trim() !== ""))}
          />
        )
      default:
        return (
          <Input
            id={id}
            className={campo.mono ? "dado" : undefined}
            value={String(bruto ?? "")}
            placeholder={placeholder}
            onChange={(e) => aoMudar(id, e.target.value)}
          />
        )
    }
  }

  return (
    <Campo nome={id} rotulo={rotulo} ajuda={campo.ajuda} erro={erro} aviso={aviso}
      nota={nota} largo={campo.largo || campo.tipo === "area"}>
      {controle()}
    </Campo>
  )
}
