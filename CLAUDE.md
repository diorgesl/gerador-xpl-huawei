# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repository holds a design document, `PLANO.md`, specifying the BGP communities policy for AS64512 and its implementation in XPL (Huawei VRP's policy language) on the NetEngine 8000 F1A, plus the app that implements it: `app/` (FastAPI, serving the JSON API under `/api`, one registry per network in `peers/<ASN>.yaml`, the generated blocks in `out/<ASN>/` and the SPA build) and `web/` (the React SPA the operator uses; `templates/` holds only the Jinja templates that render the XPL blocks). The document is written in Portuguese. The suite is `pytest` for Python and `vitest` for the front; the commands are in the `README.md`.

## Working with this document

- Keep tables and prose consistent — sections cross-reference each other. The numeric convention and polarity rules set out in "Escopo e princípios" govern every community table that follows, and the peer ID table ("Tabela de peers e IDs") is the single source of truth for values used in the `5PPA`, `6CA`, and `3xxx` sections.
- Preserve ASCII-only content in XPL comments and code blocks — the document notes that non-ASCII characters break in the TFTP/backup/diff pipeline used to move configuration.
- Many XPL snippets carry `!-` comments flagging behavior that is unverified or "to confirm with `xpl simulate`/`?` on the device" (e.g. whether `apply community {} overwrite` accepts an empty set, whether `call` returns control after an inner `finish`). Don't silently resolve these as settled fact when editing — preserve the "needs verification on hardware" framing unless the user confirms it.
- Example ASNs, IDs, and prefixes (e.g. `AS268127`, `64500`, `45.169.232.0/22`) are explicitly placeholders to be replaced with real values before publishing — don't treat them as production data.

## Structural rules encoded in the policy (must stay internally consistent when edited)

- **Numeric convention**: action communities are 3 digits (`64512:100`–`699`), informational are 4 digits (`64512:1000`–`9999`) — this is what lets a single regex strip informational communities on ingress. `64512:5PPA` (peer-specific action) is the deliberate exception: it has 4 digits but starts with `5`, so it doesn't collide with the informational-strip regex (which only matches leading digits `1`/`2`/`3`/`9`).
- **Polarity**: default is negative (announce by default; communities restrict what leaves). The `21x` range is the only positive-polarity carve-out, deliberately isolated so it doesn't mix with negative logic elsewhere — the document calls mixed polarity the root cause of route leaks.
- **Write direction**: informational communities are written only by AS64512 (anything a client sends in that namespace is discarded); action communities are written only by the client and are consumed/stripped by AS64512 before propagation. Because XPL `route-filter` only supports `overwrite`/`additive` on communities (no selective delete), stripping happens via `overwrite` as the last step of export filters — never on ingress, since that would also erase the client's not-yet-consumed action communities.
- **No IPv4/IPv6 split** in the numbering scheme — address family is already implied by the NLRI, so v4 and v6 share one namespace.
- Standard communities and their 32-bit large-community equivalents are meant to stay in sync (e.g. `64512:4:<ASN>` mirrors the `64512:5PPA` alias): when adding or changing a community, update both the standard table and, where one exists, the corresponding large-community table.

## Document map

1. **Escopo e princípios** — the five structural rules everything else follows.
2. **Mapa de faixas** — the full numeric range table (action `100`–`699`, informational `1000`–`9999`).
3. **Communities informativas** / **Communities de ação** — the community catalogs (origin, geography, learning point, RPKI/security; local preference, announcement scope, per-class/per-peer prepend, blackhole).
4. **Large communities e controle por peer** — 32-bit ASN addressing (RFC 8195) and the standard-community alias (`5PPA`) for equipment that can't send large communities.
5. **Tabela de peers e IDs** — source of truth for peer IDs referenced by `5PPA`, `6CA`, and `3xxx`; includes the template-generation note (YAML + Jinja2 + `bgpq4`).
6. **Referência de sintaxe XPL** — verified XPL parsing quirks: per-clause quoting rules, AS-path clauses vs. regex, `whole-match`, control-flow pitfalls (`approve` vs `finish`, `and`/`or` precedence, `overwrite` vs `additive`), comment syntax, and parameter scoping inside filters.
7. **Sets XPL** / **Route-filters reutilizáveis** — reusable building blocks: bogon prefix/AS-path lists, community/large-community lists, and the four shared filters (`IMPORT-SANITY`, `STRIP-EXTERNAL` — documented as impossible and kept as a record, `EXPORT-SANITY`, `STRIP-INTERNAL`).
8. **Worked examples** — full import/export filters for a transit customer, an upstream, an IX route-server session, and a PNI/CDN session, plus the legacy bugs each corrects.
9. **Originação dos próprios prefixos**, **RTBH fim a fim**, **RPKI/IRR e anti-leak**, **Migração do plano legado**, **Validação e checklist**, **Tabela pública para clientes** — origination policy, blackhole end-to-end flow, route-security layers, the legacy-to-new migration plan/timeline, a pre-production checklist, and the customer-facing policy text meant for publication (PeeringDB, LACNIC, IRR).
