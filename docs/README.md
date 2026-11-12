# ForeRSI documentation

Read the [English guide](src/content/docs/index.md) or the [Chinese guide](src/content/docs/zh-cn/index.md). The website combines usage guides, runnable workflow examples, CLI reference, and generated TypeScript API reference.

## Preview locally

Use Node.js 22.23.4 or later. From the repository root:

```bash
npm install
npm --prefix docs ci
npm run docs:dev
```

Open the local URL printed by Astro, under `/fore-rsi/`. The English guide is at `/fore-rsi/`; Chinese is at `/fore-rsi/zh-cn/`.

## Edit content

English pages live in `src/content/docs/`, with matching Chinese pages under `src/content/docs/zh-cn/`. Use the same page path in both languages. Tutorials import maintained example files so their code stays in sync.

API pages are generated from the public package entry points by TypeDoc, using the package's compiler configuration. Update source comments and exports rather than editing generated pages.

## Build the website

```bash
npm run docs:build
npm run docs:preview
```

The static site is written to `docs/dist/`. `astro.config.mjs` defines its site URL and `/fore-rsi/` base path. Deploy that directory to a static host using the matching path.
