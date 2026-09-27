import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/estilo/tokens.css"
import { quandoPerderSessao } from "./api/cliente"
import { Provedores } from "./provedores"
import { Roteador } from "./roteador"

// A sessao vencida no meio de um salvamento vira um 401 em qualquer
// chamada. O replace recarrega a pagina, e e isso que descarta o
// formulario em edicao: com um navigate do router ele sobreviveria a
// troca de tela e perderia o estado no primeiro refetch.
quandoPerderSessao(() => window.location.replace("/login"))

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provedores>
      <Roteador />
    </Provedores>
  </StrictMode>,
)
