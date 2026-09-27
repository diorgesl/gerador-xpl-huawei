import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { cliente } from "./cliente"
import { chaves, lerRecusa, type Sessao } from "./consultas"

/**
 * Quem esta logado agora. E a pergunta que a guarda faz antes de montar a
 * casca, e por isso ela nao tem retry: um servidor fora do ar nao melhora
 * na segunda tentativa, e a tela ficaria parada esperando.
 */
export function useSessao() {
  return useQuery({
    queryKey: chaves.sessao,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/sessao")
      if (error) throw new Error("falha ao ler a sessao")
      return data as Sessao
    },
    retry: false,
    staleTime: 0,
  })
}

/** A primeira mensagem da recusa, que e o que a tela de login mostra. */
export function mensagemDaRecusa(corpo: unknown): string {
  return Object.values(lerRecusa(corpo).erros)[0] ?? "nao foi possivel entrar"
}

export function useEntrar() {
  const consultas = useQueryClient()
  const navegar = useNavigate()
  return useMutation({
    mutationFn: async (credenciais: { usuario: string; senha: string }) => {
      const { data, error } = await cliente.POST("/api/login", { body: credenciais })
      if (error) throw new Error(mensagemDaRecusa(error))
      return data
    },
    onSuccess: async () => {
      // a guarda le a sessao pela chave: sem o invalidate ela continuaria
      // com o "logado: false" do primeiro render e devolveria para o login
      await consultas.invalidateQueries({ queryKey: chaves.sessao })
      navegar("/peers", { replace: true })
    },
  })
}

export function useSair() {
  const consultas = useQueryClient()
  const navegar = useNavigate()
  return useMutation({
    mutationFn: async () => {
      const { error } = await cliente.POST("/api/logout")
      if (error) throw new Error("falha ao sair")
    },
    // o onSettled, e nao o onSuccess: o cookie pode ter ido embora com uma
    // resposta que falhou, e ficar na casca mostrando o dado do cadastro e
    // pior do que sair e pedir a senha de novo
    onSettled: () => {
      consultas.clear()
      navegar("/login", { replace: true })
    },
  })
}
