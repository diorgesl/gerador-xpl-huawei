import { useState } from "react"
import { Button } from "@/components/ui/button"
import { DialogoNovoAsn } from "./DialogoNovoAsn"

/**
 * A pasta `peers/` chegou sem arquivo nenhum: nao ha rede para abrir nem
 * consulta para fazer, e o unico caminho adiante e criar o primeiro tenant.
 *
 * O caminho da pasta aparece escrito porque e ele que explica o estado: o app
 * nao tem um banco de tenants, e a lista e o que estiver na pasta do checkout,
 * um arquivo por ASN. Quem caiu aqui pode resolver pelo terminal e recarregar,
 * e o dialogo e o mesmo atalho para quem prefere a tela.
 */
export function SemTenant() {
  const [novoAberto, setNovoAberto] = useState(false)

  return (
    <div className="flex max-w-xl flex-col gap-3 p-6">
      <h1 className="text-lg font-semibold">nenhuma rede cadastrada</h1>
      <p className="text-sm text-muted-foreground">
        A pasta <span className="dado">peers/</span> do checkout está vazia. É
        dela que o app tira as redes: um arquivo por ASN, e o nome do arquivo é
        a rede - <span className="dado">peers/64512.yaml</span> é o AS64512.
      </p>
      <p className="text-sm text-muted-foreground">
        Para começar, crie o ASN da sua rede. Os peers, os grupos e os blocos
        entram depois, no cadastro dessa rede.
      </p>
      <div>
        <Button size="sm" onClick={() => setNovoAberto(true)}>criar o primeiro ASN</Button>
      </div>
      {/* o ASN novo ja vira a lista inteira daqui: quem criou o primeiro tenant
          nao tem para onde escolher, e a casca remonta com ele sozinho */}
      <DialogoNovoAsn aberto={novoAberto} aoFechar={() => setNovoAberto(false)}
                      aoCriar={() => setNovoAberto(false)} />
    </div>
  )
}
