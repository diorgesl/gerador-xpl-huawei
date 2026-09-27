import "@testing-library/jest-dom/vitest"

// o jsdom nao implementa execCommand, e o teste da copia precisa espiona-lo.
// O retorno falso e o comportamento honesto: o jsdom nao copia nada, e quem
// quiser o caminho de sucesso sobrescreve com o mock
if (!document.execCommand) {
  document.execCommand = () => false
}

// o jsdom nao implementa matchMedia: sem isto, todo teste que toca no tema
// estoura com "window.matchMedia is not a function"
if (!window.matchMedia) {
  window.matchMedia = ((consulta: string) => ({
    matches: false,
    media: consulta,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}
