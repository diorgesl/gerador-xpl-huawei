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
