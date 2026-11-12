// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightTypeDoc, { typeDocSidebarGroup } from "starlight-typedoc";

export default defineConfig({
  site: "https://shiweijiezero.github.io",
  base: "/fore-rsi",
  integrations: [
    starlight({
      title: "ForeRSI",
      favicon: "/favicon.svg",
      logo: {
        light: "./assets/fore-rsi-light.png",
        dark: "./assets/fore-rsi-dark.png",
        replacesTitle: true,
      },
      description: "Guides and API reference for ForeRSI.",
      defaultLocale: "root",
      locales: {
        root: { label: "English", lang: "en" },
        "zh-cn": { label: "简体中文", lang: "zh-CN" },
      },
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/shiweijiezero/fore-rsi" }],
      editLink: { baseUrl: "https://github.com/shiweijiezero/fore-rsi/edit/main/docs/" },
      customCss: ["./src/styles/custom.css"],
      sidebar: [
        { label: "Overview", slug: "index", translations: { "zh-CN": "概览" } },
        { label: "Get started", slug: "getting-started", translations: { "zh-CN": "快速开始" } },
        {
          label: "Guides",
          translations: { "zh-CN": "使用指南" },
          items: [
            { label: "Task files", slug: "guides/tasks", translations: { "zh-CN": "任务文件" } },
            { label: "Models and authentication", slug: "guides/models", translations: { "zh-CN": "模型与登录" } },
            { label: "Sessions", slug: "guides/sessions", translations: { "zh-CN": "会话管理" } },
          ],
        },
        {
          label: "Develop workflows",
          translations: { "zh-CN": "开发工作流" },
          items: [
            { label: "Define and load a workflow", slug: "tutorials/workflow", translations: { "zh-CN": "定义与加载工作流" } },
            { label: "Task data", slug: "reference/task-data", translations: { "zh-CN": "任务数据" } },
          ],
        },
        { label: "CLI reference", slug: "reference/cli", translations: { "zh-CN": "命令行参考" } },
        typeDocSidebarGroup,
      ],
      plugins: [
        starlightTypeDoc({
          entryPoints: ["../src/index.ts", "../src/app/workflow-loader.ts"],
          tsconfig: "../tsconfig.json",
          output: "api",
          sidebar: { label: "API", collapsed: true },
          typeDoc: {
            name: "ForeRSI API",
            entryFileName: "index",
            readme: "none",
            excludePrivate: true,
            excludeInternal: true,
            sourceLinkTemplate: "https://github.com/shiweijiezero/fore-rsi/blob/main/{path}#L{line}",
          },
        }),
      ],
    }),
  ],
});
