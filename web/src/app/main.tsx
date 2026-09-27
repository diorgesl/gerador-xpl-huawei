import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/estilo/tokens.css"
import { Provedores } from "./provedores"
import { Roteador } from "./roteador"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provedores>
      <Roteador />
    </Provedores>
  </StrictMode>,
)
