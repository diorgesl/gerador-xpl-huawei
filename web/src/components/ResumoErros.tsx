import { CircleAlert } from "lucide-react"
import { camposDoErro, SECOES_GRUPO, SECOES_PEER } from "@/lib/campos"

type Props = {
  erros: Record<string, string>
  tipo: string
  deGrupo?: boolean
  aoIrPara: (campo: string | null, secao: string | null) => void
}

export function ResumoErros({ erros, tipo, deGrupo = false, aoIrPara }: Props) {
  const secoes = deGrupo ? SECOES_GRUPO : SECOES_PEER
  const itens = Object.entries(erros).filter(([, mensagem]) => mensagem)
  if (itens.length === 0) return null

  return (
    <div role="alert" className="rounded border border-erro-texto/30 bg-erro-fundo p-2 text-erro-texto">
      <p className="flex items-center gap-1 text-[13px] font-medium">
        <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
        {itens.length === 1 ? "1 erro impede o salvar" : `${itens.length} erros impedem o salvar`}
      </p>
      <ul className="mt-1 space-y-0.5 text-xs">
        {itens.map(([chave, mensagem]) => {
          const campos = camposDoErro(chave, tipo, deGrupo)
          // Um campo so: vai nele. Varios: a mensagem nao diz qual deles esta
          // torto (o `prefixo invalido` de v4 e o de v6 saem na mesma chave), e
          // prometer o primeiro era pior que levar ao topo da secao que os tem
          const campo = campos.length === 1 ? campos[0] : null
          const secao = campos.length > 0
            ? secoes.find((s) => campos.every((c) => s.campos.includes(c)))?.id ?? null
            : null
          return (
            <li key={chave}>
              {campos.length > 0 ? (
                <button
                  type="button"
                  className="text-left underline decoration-dotted"
                  onClick={() => aoIrPara(campo, secao)}
                >
                  {mensagem}
                </button>
              ) : (
                <span>{mensagem}</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
