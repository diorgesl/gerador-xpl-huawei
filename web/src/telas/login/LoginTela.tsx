import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useEntrar } from "@/api/sessao"

/**
 * A entrada do app, fora da casca: quem ainda nao entrou nao tem lista de
 * peers para ver, e a barra lateral mostraria justamente o que o login
 * esconde.
 *
 * O campo do usuario ja vem preenchido com "admin" porque e o unico que o
 * boot cria. A senha fica no estado da tela ate a resposta, e nao vai para
 * lugar nenhum alem do POST.
 */
export function LoginTela() {
  const [usuario, setUsuario] = useState("admin")
  const [senha, setSenha] = useState("")
  const entrar = useEntrar()

  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <form
        className="w-full max-w-sm rounded border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault()
          entrar.mutate({ usuario, senha })
        }}
      >
        <h1 className="text-lg font-semibold">bgpgen</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          o cadastro e os blocos gerados ficam atrás do login
        </p>

        <div className="mt-4 flex flex-col gap-1">
          <Label htmlFor="usuario">Usuário</Label>
          <Input id="usuario" value={usuario} autoComplete="username"
                 onChange={(e) => setUsuario(e.target.value)} />
        </div>

        <div className="mt-3 flex flex-col gap-1">
          <Label htmlFor="senha">Senha</Label>
          <Input id="senha" type="password" value={senha}
                 autoComplete="current-password"
                 onChange={(e) => setSenha(e.target.value)} />
        </div>

        {entrar.isError ? (
          <p role="alert" className="mt-3 text-sm text-erro-texto">
            {entrar.error.message}
          </p>
        ) : null}

        <Button type="submit" className="mt-4 w-full" disabled={entrar.isPending}>
          entrar
        </Button>
      </form>
    </div>
  )
}
