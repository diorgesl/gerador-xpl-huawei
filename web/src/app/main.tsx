import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/estilo/tokens.css"
import { quandoPerderSessao } from "@/api/cliente"
import { Provedores } from "./provedores"
import { Roteador } from "./roteador"

// A sessao vencida no meio de um salvamento vira um 401 em qualquer
// chamada. O replace recarrega a pagina, e e isso que descarta o
// formulario em edicao: com um navigate do router ele sobreviveria a
// troca de tela e perderia o estado no primeiro refetch.
//
// Quem ja esta no login nao recarrega nada: ali o 401 e a resposta
// esperada de quem ainda nao entrou. O ProvedorTenant monta fora do
// router, entao a lista de ASNs e pedida em toda tela, esta inclusive, e
// sem a guarda cada 401 recarrega a pagina, o provedor pergunta de novo e
// o formulario de login nunca chega a ser desenhado.
quandoPerderSessao(() => {
  if (window.location.pathname === "/login") return
  window.location.replace("/login")
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provedores>
      <Roteador />
    </Provedores>
  </StrictMode>,
)
