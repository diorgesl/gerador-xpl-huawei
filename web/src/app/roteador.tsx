import { createBrowserRouter, RouterProvider } from "react-router-dom"
import { Casca } from "./casca"
import { NaoEncontrado } from "@/telas/NaoEncontrado"

// Cada tela entra aqui na task que a cria: a rota de /peers vem junto com a
// lista, a de /grupos com a tela de grupo, e assim por diante. Ate la o link
// da barra lateral cai no NaoEncontrado, que e uma tela de verdade e nao um
// lugar reservado.
export const roteador = createBrowserRouter([
  {
    path: "/",
    element: <Casca />,
    children: [
      { index: true, element: <NaoEncontrado /> },
      { path: "*", element: <NaoEncontrado /> },
    ],
  },
])

export function Roteador() {
  return <RouterProvider router={roteador} />
}
