import { createBrowserRouter, RouterProvider } from "react-router-dom"
import { Casca } from "./casca"
import { NaoEncontrado } from "@/telas/NaoEncontrado"
import { PeerTela, TelaDoPeer } from "@/telas/peers/PeerTela"
import { GrupoTela, TelaDoGrupo } from "@/telas/grupos/GrupoTela"
import { PrefixosTela } from "@/telas/prefixos/PrefixosTela"
import { BaseTela } from "@/telas/base/BaseTela"
import { ConfiguracoesTela } from "@/telas/configuracoes/ConfiguracoesTela"

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
      // "peers/:id" sem precisar de ordem no arquivo. A rota por id usa o
      // TelaDoPeer, e a do grupo pelo TelaDoGrupo, que remontam a tela na troca
      // de registro: o elemento e reusado quando so o :id muda, e o formulario
      // sobreviveria com os valores do registro anterior
      { path: "peers", element: <PeerTela /> },
      { path: "peers/novo", element: <PeerTela /> },
      { path: "peers/:id", element: <TelaDoPeer /> },
      { path: "grupos", element: <GrupoTela /> },
      { path: "grupos/novo", element: <GrupoTela /> },
      { path: "grupos/:id", element: <TelaDoGrupo /> },
      { path: "prefixos", element: <PrefixosTela /> },
      { path: "base", element: <BaseTela /> },
      { path: "configuracoes", element: <ConfiguracoesTela /> },
      { path: "*", element: <NaoEncontrado /> },
    ],
  },
])

export function Roteador() {
  return <RouterProvider router={roteador} />
}
