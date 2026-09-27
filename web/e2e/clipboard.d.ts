/**
 * O unico global de navegador que o e2e usa fora do ES2022.
 *
 * A lib deste projeto e a ES2022, e nao a DOM: sem ela `document`, `window` e
 * `localStorage` deixam de typecheckar no `e2e/`, que e o ponto de ter o
 * `"lib": ["ES2022"]` no tsconfig.e2e.json - o spec roda no navegador, mas quem
 * o escreve nao pode contar com a API do app. O `clipboard` e a excecao, porque
 * e por ele que os casos conferem o que a copia levou, e o que se declara aqui e
 * so o que eles usam: o `readText`, e nada mais.
 */
interface Navigator {
  readonly clipboard: { readText(): Promise<string> }
}
