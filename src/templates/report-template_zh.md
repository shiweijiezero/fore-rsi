# 报告

[English](report-template-mod.md) | 简体中文

- 本报告既是给用户的进化叙事，也作为可复用知识的索引：每个探索方向（含失败）都产出或更新一条知识库条目。
- 单轮命令与原始结果留在实验记录中。

## 版本迭代

<!-- 在此放入 figures/progress/ 中生成的里程碑图和搜索图。 -->

| 版本 | 配置选项 | TPOT ms | TTFT ms | 吞吐 token/s | 证据 |
| --- | --- | ---: | ---: | ---: | --- |
| 上一轮最优版本（本轮 baseline） | 沿用上一轮配置 | 实测值 | 实测值 | 实测值 | [实验记录](iterations/<name>/notes/iteration.md) |
| +A + B| 本轮改动组 合 | 实测值（相对 baseline ±%） | 实测值（相对 baseline ±%） | 实测值（相对 baseline ±%） | [实验记录](iterations/<name>/notes/iteration.md) |  

## 探索方向

- 方向可以是单项改动或改动组合，失败和未采用的方向同样列出。
- 提案状态取自该方向 `progress.yaml`，并与 `figures/progress/progress-summary.md` 一致；
- 决策原因只写简要结论，完整诊断见该方向的 `iteration.md`。

| 轮次 | 父节点 | 方向 | 方向简述 | 提案（链接） | 提案状态 | 采用状态 | 决策原因（简述） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | baseline | [qkv-views](iterations/qkv-views/notes/iteration.md) | 一句话说明改动对象和手段 | [proposal](iterations/qkv-views/notes/proposal.md) | valid | 采用 | 实测收益满足本轮目标 |
| 0 | baseline | [moe-overlap](iterations/moe-overlap/notes/iteration.md) | 一句话说明改动对象和手段 | [proposal](iterations/moe-overlap/notes/proposal.md) | runtime_failed | 不采用 | 运行失败，未获得有效测量 |

## 知识沉淀

每个探索方向，无论成败，都产出或更新一条可复用知识；本节只登记结果类型与链接，机制、适用条件、失败原因与可复用代码写在 [知识条目模板](guidance-template_zh.md) 里，存入 [知识库](../guidance/knowledge/README_zh.md)。

| 知识条目 | 结果类型 | 机制 / 适用条件 / 边界 | 链接 |
| --- | --- | --- | --- |
| QKV 视图替代 reshape | 正结果 | 消除显存拷贝，吞吐 +10.4%；适用 decode 阶段、BF16 | [条目](../guidance/knowledge/<分类>/<条目>_zh.md) |
| 低精度近似 attention | 负结果 | 吞吐 +42.4% 但质量不通过，适用边界 = 质量敏感负载 | [条目](../guidance/knowledge/<分类>/<条目>_zh.md) |
| qkv-views + cuda-graph 耦合 | 正结果 | 共享启动路径，合并时保留某侧 | [条目](../guidance/knowledge/<分类>/<条目>_zh.md) |
