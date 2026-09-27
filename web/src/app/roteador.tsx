import { createBrowserRouter, RouterProvider } from "react-router-dom"
import { Casca } from "./casca"
import { NaoEncontrado } from "@/telas/NaoEncontrado"
import { PeerTela } from "@/telas/peers/PeerTela"

// Cada tela entra aqui na task que a cria: a rota de /peers vem junto com a
// lista, a de /grupos com a tela de grupo, e assim por diante. Ate la o link
// da barra lateral cai no NaoEncontrado, que e uma tela de verdade e nao um
// lugar reservado.
//
// O router fica sem export: constante e componente no mesmo arquivo quebra o
// fast refresh, e so o Roteador abaixo usa este objeto. Ele e criado no modulo,
// e nao dentro do componente, para nao ser recriado a cada render.
const roteador = createBrowserRouter([
  {
    path: "/",
    element: <Casca />,
    children: [
      { index: true, element: <NaoEncontrado /> },
      // O React Router ordena por especificidade, entao "peers/novo" ganha de
      // "peers/:id" sem precisar de ordem no arquivo
      { path: "peers", element: <PeerTela /> },
      { path: "peers/novo", element: <PeerTela /> },
      { path: "peers/:id", element: <PeerTela /> },
      { path: "*", element: <NaoEncontrado /> },
    ],
  },
])

export function Roteador() {
  return <RouterProvider router={roteador} />
}
