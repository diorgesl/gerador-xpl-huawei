import { Navigate, createBrowserRouter, RouterProvider } from "react-router-dom"
import { Casca } from "./casca"
import { ExigeLogin } from "./ExigeLogin"
import { LoginTela } from "@/telas/login/LoginTela"
import { NaoEncontrado } from "@/telas/NaoEncontrado"
import { Inicio } from "@/telas/Inicio"
import { PeerTela, TelaDoPeer } from "@/telas/peers/PeerTela"
import { GrupoTela, TelaDoGrupo } from "@/telas/grupos/GrupoTela"
import { PrefixosTela } from "@/telas/prefixos/PrefixosTela"
import { BaseTela } from "@/telas/base/BaseTela"
import { ConfigTela } from "@/telas/config/ConfigTela"
import { ConfiguracoesTela } from "@/telas/configuracoes/ConfiguracoesTela"

// Cada tela entrou aqui na task que a criou, e a lista dos registros nao e uma
// delas: ela e a barra lateral, que a casca monta em toda rota. O que mora em
// /peers e /grupos e a tela de chegada, para quem abre o app sem registro
// aberto.
//
// O router fica sem export: constante e componente no mesmo arquivo quebra o
// fast refresh, e so o Roteador abaixo usa este objeto. Ele e criado no modulo,
// e nao dentro do componente, para nao ser recriado a cada render.
const roteador = createBrowserRouter([
  // A tela de login fica fora da casca e fora da guarda: ela e o destino de
  // quem nao entrou, e a guarda a mandaria para si mesma
  { path: "/login", element: <LoginTela /> },
  {
    path: "/",
    element: (
      <ExigeLogin>
        <Casca />
      </ExigeLogin>
    ),
    children: [
      // Em producao quem responde / e o uvicorn, com um 307 para /peers. Com o
      // Vite na 5173 esse redirect nao existe, e sem esta rota o modo de
      // desenvolvimento documentado no README abre o NaoEncontrado
      { index: true, element: <Navigate to="/peers" replace /> },
      // O React Router ordena por especificidade, entao "peers/novo" ganha de
      // "peers/:id" sem precisar de ordem no arquivo. A rota por id usa o
      // TelaDoPeer, e a do grupo pelo TelaDoGrupo, que remontam a tela na troca
      // de registro: o elemento e reusado quando so o :id muda, e o formulario
      // sobreviveria com os valores do registro anterior
      //
      // A rota da lista e a da chegada, e nao um formulario em branco: quem cria
      // e /peers/novo, que e para onde o "+ novo" da barra leva
      { path: "peers", element: <Inicio oQue="peer" /> },
      { path: "peers/novo", element: <PeerTela /> },
      { path: "peers/:id", element: <TelaDoPeer /> },
      { path: "grupos", element: <Inicio oQue="grupo" /> },
      { path: "grupos/novo", element: <GrupoTela /> },
      { path: "grupos/:id", element: <TelaDoGrupo /> },
      { path: "prefixos", element: <PrefixosTela /> },
      { path: "base", element: <BaseTela /> },
      // o nome e comprido de proposito: "config" ao lado de "configuracoes"
      // seriam dois links com o mesmo comeco, um do outro
      { path: "config-completa", element: <ConfigTela /> },
      { path: "configuracoes", element: <ConfiguracoesTela /> },
      { path: "*", element: <NaoEncontrado /> },
    ],
  },
])

export function Roteador() {
  return <RouterProvider router={roteador} />
}
