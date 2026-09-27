import { Link } from "react-router-dom"

export function NaoEncontrado() {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">Registro não encontrado</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        O peer ou grupo pode ter sido excluído em outra aba, ou o endereço está errado.
      </p>
      <Link to="/peers" className="mt-3 inline-block text-sm underline">
        voltar para os peers
      </Link>
    </div>
  )
}
