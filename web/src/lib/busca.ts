import type { GrupoResumo, PeerResumo } from "@/api/consultas"

/** O filtro da busca da barra lateral: ASN, apelido, nome e tipo. */
export function filtrarPeers(peers: PeerResumo[], termo: string): PeerResumo[] {
  const t = termo.trim().toLowerCase()
  if (!t) return peers
  return peers.filter(
    (p) =>
      String(p.asn).includes(t) ||
      p.apelido.toLowerCase().includes(t) ||
      p.nome.toLowerCase().includes(t) ||
      p.tipo.toLowerCase().includes(t),
  )
}

export function filtrarGrupos(grupos: GrupoResumo[], termo: string): GrupoResumo[] {
  const t = termo.trim().toLowerCase()
  if (!t) return grupos
  return grupos.filter(
    (g) => g.nome.toLowerCase().includes(t) || g.tipo.toLowerCase().includes(t),
  )
}

// A ordem da lista lateral: quem leva trafego para fora primeiro, os clientes
// por ultimo. Dentro do tipo fica a ordem do cadastro (o sort e estavel), e um
// tipo fora da lista vai para o fim em vez de sumir
const ORDEM_TIPO = ["upstream", "ix", "pni", "parceiro", "cliente"]

export function ordenarPeers(peers: PeerResumo[]): PeerResumo[] {
  const posicao = (tipo: string) => {
    const i = ORDEM_TIPO.indexOf(tipo)
    return i === -1 ? ORDEM_TIPO.length : i
  }
  return [...peers].sort((a, b) => posicao(a.tipo) - posicao(b.tipo))
}
