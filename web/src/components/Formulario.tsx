import { useState, type ReactNode } from "react"
import { useWatch, type FieldValues, type Path, type UseFormReturn } from "react-hook-form"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { AdicionarCommunity } from "@/components/AdicionarCommunity"
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
  // as origens candidatas do reaproveitamento, montadas pela tela: o
  // formulario so as repassa ao campo que as declarou (`origens: true`)
  origens?: Opcao[]
  // a nota do reaproveitamento vai no topo da secao de politica, e nao no
  // campo: os campos de politica continuam a vista, e a nota e sobre todos
  notaDaPolitica?: string
  // quem cede politica carrega o token que nomeia os filtros que o outro
  // chama: a renomeacao acontece no formulario da ORIGEM, e e la que o aviso
  // aparece
  avisoDoToken?: string
  // A tela reage a edicao de um campo que o formulario so repassa (o
  // reaproveitamento limpa a origem escolhida quando o tipo ou o ASN muda). O
  // formulario nao sabe de campo nenhum: ele conta que o campo mudou, e quem
  // decide o que fazer e quem tem a lista
  aoEditarCampo?: (campo: string, valor: unknown) => void
  erros: Record<string, string>
  avisos: Aviso[]
  deGrupo?: boolean
  aoIrPara: (campo: string | null, secao: string | null) => void
  // A secao de prefixos tem os botoes de consultar o IRR, que sao acao da tela
  // e nao do formulario: quem desenha a secao e o Formulario, e quem sabe o que
  // fazer com o resultado e a tela
  acaoDaSecao?: (secao: Secao) => ReactNode
}

export function Formulario<T extends FieldValues>({
  form, campos, secoes, camposPorTipo, cascataCampos, plano, grupos, origens, notaDaPolitica,
  avisoDoToken, aoEditarCampo, erros, avisos, deGrupo = false, aoIrPara, acaoDaSecao,
}: Props<T>) {
  // o retrato deste render: a cascata le o formulario daqui, e o `visivel` sai
  // do mesmo lugar. O `as` e porque o useWatch devolve o formulario inteiro
  // sem tipo, e o Valores e a forma que o campos.ts entende
  const valores = useWatch({ control: form.control }) as unknown as Valores
  const tipo = String(valores.tipo ?? "cliente")
  const contagem = secoesComErro(erros, tipo, deGrupo, secoes)
  // o grupo nao tem reaproveitamento: sem lista a prop pode faltar
  const ctx: Contexto = { plano, tipo, grupos, origens: origens ?? [] }

  // A mesma lista serve o indice e os fieldsets, e a secao sem campo visivel
  // sai das duas: quem decide se ela existe na tela e o campo dentro dela
  const visiveisPorSecao = secoes
    .map((secao) => ({
      secao,
      visiveis: campos.filter(
        (c) => c.secao === secao.id && visivel(c.nome, valores, erros, camposPorTipo, tipo, deGrupo),
      ),
    }))
    .filter((s) => s.visiveis.length > 0)

  // o `por` e o caminho da edicao do operador, e so ele: o reset do registro
  // salvo e a consulta ao IRR escrevem no formulario por fora daqui, e uma
  // regra presa a edicao nao pode disparar neles
  const por = (nome: string, valor: unknown) => {
    form.setValue(nome as Path<T>, valor as never, { shouldDirty: true })
    aoEditarCampo?.(nome, valor)
  }

  // A cascata devolve o formulario inteiro, com os campos que a troca tocou ja
  // com o valor novo. Escrever tudo de volta reescreveria tambem os campos que
  // a cascata NAO tocou, com o retrato de antes da edicao - e a escolha de
  // origem que a troca de tipo acabou de limpar voltaria com ele. So o que a
  // cascata mudou sobe: o que nao mudou ja esta no formulario.
  function aplicarCascata(novos: Valores, pular: string[]) {
    for (const [nome, valor] of Object.entries(novos)) {
      if (pular.includes(nome) || valor === valores[nome]) continue
      por(nome, valor)
    }
  }

  // A cascata roda aqui: o select do tipo nao sabe o que fazer com o resto do
  // modelo, e o campo que ainda esta no default do tipo anterior e o unico que
  // se move.
  function aoTrocarTipo(novo: string) {
    const novos = cascata(tipo, novo, valores, plano.padroes, cascataCampos, String(valores.classe ?? ""))
    por("tipo", novo)
    aplicarCascata(novos, ["tipo", "classe"])
  }

  function aoTrocarClasse(nova: string) {
    // O `valores` do `useWatch` e o retrato deste render, entao a classe nova
    // ainda nao esta nele. A cascata le a classe de dentro do objeto para
    // comparar com a anterior, e sem a troca aqui a comparacao seria "a classe
    // mudou?" com o mesmo valor dos dois lados, que nunca e verdade: a origem
    // do downstream ficaria presa na comunidade da classe anterior
    const classeAntes = String(valores.classe ?? "")
    const novos = cascata(tipo, tipo, { ...valores, classe: nova }, plano.padroes, [], classeAntes)
    aplicarCascata(novos, ["classe", "tipo"])
  }

  return (
    <div className="flex flex-col gap-4">
      <ResumoErros erros={erros} tipo={tipo} deGrupo={deGrupo} aoIrPara={aoIrPara} />

      {/* O indice e os fieldsets saem da MESMA lista: uma secao sem campo
          visivel nao vira fieldset, e um link para ela nao levaria a lugar
          nenhum (o peer novo nao tem campo em "te" nem em "aspath") */}
      <nav aria-label="Seções do formulário" className="flex flex-wrap gap-2 text-xs">
        {visiveisPorSecao.map(({ secao }) => (
          <a key={secao.id} href={`#secao-${secao.id}`} className="rounded border px-2 py-0.5 hover:bg-accent">
            {/* o espaco entre as duas expressoes tem que estar escrito, e na
                mesma linha: o JSX come o texto que so tem espaco e quebra de
                linha, e o nome acessivel sairia "Identificacao(1)" */}
            {secao.rotulo} {contagem[secao.id] > 0 && <span className="text-erro-texto">({contagem[secao.id]})</span>}
          </a>
        ))}
      </nav>

      {visiveisPorSecao.map(({ secao, visiveis }) => (
        <fieldset key={secao.id} id={`secao-${secao.id}`} className="rounded border p-3">
          <legend className="px-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            {secao.rotulo}
          </legend>
          {secao.id === "politica" && notaDaPolitica && (
            <p className="px-2 pb-1 text-xs text-muted-foreground">{notaDaPolitica}</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visiveis.map((campo) => (
              <CampoRender
                key={campo.nome}
                campo={campo}
                ctx={ctx}
                bruto={valores[campo.nome]}
                erro={erroDoCampo(campo.nome, erros, tipo, deGrupo)}
                avisos={avisos.filter((a) => a.campo === campo.nome).map((a) => a.mensagem)}
                nota={campo.nome === "apelido" && avisoDoToken
                  ? avisoDoToken
                  : pertenceAoTipo(campo.nome, camposPorTipo, tipo)
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
      ))}
    </div>
  )
}

function linhasDe(valor: unknown): string[] {
  return Array.isArray(valor) ? (valor as string[]) : []
}

/**
 * O campo de lista, uma entrada por linha.
 *
 * O texto cru mora aqui, no rascunho, e nao no array: com o `value` saindo do
 * array filtrado, a quebra de linha digitada some (o Enter vira "\n", o filtro
 * tira, e o React reescreve o campo sem ela), e a linha seguinte cola na
 * anterior. Medido: digitar "a", Enter, "b" deixava o campo com "ab" no lugar
 * de "a\nb". O array filtrado sobe a cada tecla, entao a previa continua ao
 * vivo.
 *
 * O que se mostra e o rascunho enquanto ele representar o mesmo array que o
 * formulario tem, e o valor do formulario quando nao representa mais: o reset
 * do salvar e a consulta ao IRR escrevem no formulario, e nao na tela, e o
 * campo tem que acompanhar. A escolha sai do render, e nao de um efeito que
 * chama setState: essa forma e erro nesta configuracao
 * (react-hooks/set-state-in-effect), e a derivacao nao sincroniza estado
 * nenhum.
 */
function AreaTexto({ id, bruto, linhas, mono, aoMudar }: {
  id: string
  bruto: unknown
  linhas: number
  mono?: boolean
  aoMudar: (nome: string, valor: unknown) => void
}) {
  const externo = linhasDe(bruto).join("\n")
  const [texto, setTexto] = useState(externo)
  const digitado = texto.split("\n").filter((l) => l.trim() !== "").join("\n")
  const valor = digitado === externo ? texto : externo

  return (
    <Textarea
      id={id}
      rows={linhas}
      spellCheck={false}
      className={mono ? "dado" : undefined}
      value={valor}
      onChange={(e) => {
        setTexto(e.target.value)
        aoMudar(id, e.target.value.split("\n").filter((l) => l.trim() !== ""))
      }}
    />
  )
}

function CampoRender({ campo, ctx, bruto, erro, avisos, nota, aoMudar, aoTrocarTipo, aoTrocarClasse }: {
  campo: CampoTabela
  ctx: Contexto
  bruto: unknown
  erro?: string
  avisos?: string[]
  nota?: string
  aoMudar: (nome: string, valor: unknown) => void
  aoTrocarTipo: (tipo: string) => void
  aoTrocarClasse: (classe: string) => void
}) {
  const id = campo.nome
  const base = campo.origens ? ctx.origens : (campo.opcoes?.(ctx) ?? [])
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
            <SelectTrigger id={id} className="w-full min-w-0">
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
          <>
            {/* a busca fica acima do campo e nao no lugar dele: o textarea
                continua livre, e quem sabe o numero digita direto */}
            {campo.sugestoes && (
              <AdicionarCommunity
                rotulo={campo.rotulo}
                sugestoes={ctx.plano.sugestoes[campo.sugestoes]}
                jaUsadas={linhasDe(bruto)}
                aoAdicionar={(valor) => aoMudar(id, [...linhasDe(bruto), valor])}
              />
            )}
            <AreaTexto
              id={id}
              bruto={bruto}
              linhas={campo.linhas ?? 3}
              mono={campo.mono}
              aoMudar={aoMudar}
            />
          </>
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
    <Campo nome={id} rotulo={rotulo} ajuda={campo.ajuda} erro={erro} avisos={avisos}
      nota={nota} largo={campo.largo || campo.tipo === "area"}>
      {controle()}
    </Campo>
  )
}
