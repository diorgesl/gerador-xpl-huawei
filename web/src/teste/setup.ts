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

// O jsdom nao implementa Request, e o do Node recusa URL relativa, que e a
// forma que o openapi-fetch monta (baseUrl vazio + o caminho do schema). Este
// duble guarda o que o cliente le depois de montar o pedido.
class Requisicao {
  url: string
  method: string
  headers: Headers
  body: BodyInit | null | undefined

  constructor(entrada: string, init: RequestInit = {}) {
    this.url = String(entrada)
    this.method = init.method ?? "GET"
    this.headers = new Headers(init.headers)
    this.body = init.body
  }

  async json() {
    return JSON.parse(String(this.body ?? "null"))
  }

  async text() {
    return String(this.body ?? "")
  }
}

globalThis.Request = Requisicao as unknown as typeof Request

// as primitivas do shadcn usam estas tres APIs, que o jsdom nao tem
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}
