import "@testing-library/jest-dom/vitest"

// o jsdom nao implementa execCommand, e o teste da copia precisa espiona-lo.
// O retorno falso e o comportamento honesto: o jsdom nao copia nada, e quem
// quiser o caminho de sucesso sobrescreve com o mock
if (!document.execCommand) {
  document.execCommand = () => false
}
