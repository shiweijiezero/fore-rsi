# SGLang throughput optimization

## Task requirements

- Target model: `Qwen/Qwen3.5-35B-A3B`. [Fixed]
- Inference engine: SGLang, using the MetaX-compatible environment supplied for the task. [Fixed]
- Optimization objectives: increase aggregate output throughput (tokens/s) and reduce mean time per output token (TPOT, ms/token) at request concurrency 1 and 16. Report each concurrency separately. [Fixed]
- Precision: BF16. [Fixed]
- Starting configuration: two-way tensor parallelism (TP2) and a 262,144-token context. Parallelism, context length, cache settings, and stage placement may change while preserving the evaluation workloads and fixed requirements.
- Final deployment budget: at most 2 MetaX C500 GPUs on one host. Target-model, auxiliary-model, and frontend workloads together must stay within 32 CPU cores and 250G host memory, counted from their container resource limits. [Fixed]
- Experiment sizing: service candidates must fit the final deployment budget. Kernel, compilation, and correctness experiments may use fewer resources, including one GPU.
- Available resources: at most 4 MetaX GPUs across all experiments. Schedule CPU, memory, and storage within actual host capacity and the cluster, namespace, and host access provided at task startup. [Fixed]
- Allowed changes: implementation and configuration at any layer within the fixed requirements and authorized resources, including algorithms, auxiliary models and their weights, and execution layout.
- Work duration: a total budget of 24 hours from the start of task execution. [Fixed]

## Agent team

- 4 Explorers investigate bottlenecks, compare approaches, and propose experiments.
- 4 Workers implement selected approaches.
- 2 Verifiers deploy candidates, measure performance, and check correctness and answer quality.
- Coordinator and Checker use the workflow's role settings. The Watchdog reviews progress and handoffs every hour.
- Use the harness, model, and reasoning settings assigned to each role for this task. Unspecified execution settings inherit the Coordinator's current settings.

## Deployment and measurement

- Give each candidate its own source checkout, service address, and iteration name. Keep that binding for deployment and measurement; repeat measurements use the same iteration.
- After changing source or configuration, deploy the candidate and confirm that the intended source and settings are active before measuring it. Reuse compatible build environments, images, model files, and caches.
- Use random workloads for routine iterations, StudyChat for multi-turn hypotheses and final review, and GSM8K when a change needs additional answer-quality evidence. Reuse results obtained under matching conditions.
- Match datasets, request ranges, random seeds, concurrency, and sampling settings between a candidate and its controls. Keep additional diagnostics separate from the specified workloads.
- Report aggregate output tokens/s and mean TPOT (ms/token) separately for C1, C16, and each workload. Include failures and regressions; do not combine the groups into a weighted score.
- Preserve the first measured configuration as the original comparison. Record each candidate's actual parent and report changes against both the original comparison and that parent.

## Shared task configuration

Initialize these values once in the task's working directory, before switching to candidate checkouts. Every candidate uses the same absolute results directory. The execution environment supplies `WANDB_API_KEY`.

```bash
export MODEL_ID="Qwen/Qwen3.5-35B-A3B"
export RESULTS_DIR="$PWD/results/qwen3.5-35b-a3b-sglang-c500"
export WANDB_PROJECT="fore-rsi-inference"
export WANDB_GROUP="qwen35-sglang-c500-bf16"
```

Measurements use the Foretoken CLI against SGLang's OpenAI-compatible endpoint. The benchmark client must have access to the model's tokenizer and the selected datasets.

## Deploy a candidate

Run from the candidate's SGLang source root, in its allocated environment with the corresponding GPU visibility and container resource limits. Use the environment's process or job manager to keep the service running during measurements. Rebuild changed compiled components through SGLang's native build path.

The initial candidate uses the following settings. Parallel candidates choose distinct service ports and iteration names. The loopback example assumes the server and benchmark client share a network namespace. For a separate client, configure the server's listening address and set `MODEL_SERVICE_URL` to the authorized service endpoint.

```bash
export ITERATION="tp2-bf16"
export SGLANG_PORT=30000
export MODEL_SERVICE_URL="http://127.0.0.1:${SGLANG_PORT}/v1/chat/completions"

PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}" \
  python -m sglang.launch_server \
  --model-path "$MODEL_ID" --served-model-name "$MODEL_ID" \
  --dtype bfloat16 --tp-size 2 --context-length 262144 \
  --host 127.0.0.1 --port "$SGLANG_PORT"
```

## Evaluate

### Routine performance: random

```bash
for concurrency in 1 16; do
  foretoken perf --url "$MODEL_SERVICE_URL" --model "$MODEL_ID" --dataset random \
    --min-prompt-length 128 --max-prompt-length 4096 \
    --min-output-length 128 --max-output-length 512 \
    --max-concurrency "$concurrency" --num-prompts 80 --warmup-requests 4 \
    --random-seed 0 --temperature 0 --output experiment,raw,wandb \
    --output-dir "$RESULTS_DIR" --iteration "$ITERATION" \
    --wandb-project "$WANDB_PROJECT" --wandb-group "$WANDB_GROUP" \
    --wandb-run-name "${ITERATION}-random-c${concurrency}"
done
```

### Multi-turn hypotheses and final review: StudyChat

```bash
for concurrency in 1 16; do
  foretoken perf --url "$MODEL_SERVICE_URL" --model "$MODEL_ID" \
    --dataset hf://datasets/KrisQ/StudyChat/data.jsonl \
    --max-concurrency "$concurrency" --num-prompts 200 --max-tokens 2048 \
    --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb \
    --output-dir "$RESULTS_DIR" --iteration "$ITERATION" \
    --wandb-project "$WANDB_PROJECT" --wandb-group "$WANDB_GROUP" \
    --wandb-run-name "${ITERATION}-studychat-c${concurrency}"
done
```

### Answer quality when needed: GSM8K

```bash
foretoken eval --url "$MODEL_SERVICE_URL" --model "$MODEL_ID" \
  --evaluator lm-eval --tasks gsm8k --num_fewshot 0 --limit 20 \
  --model_args num_concurrent=64,max_gen_toks=32768 \
  --output experiment,plot,wandb \
  --output-dir "$RESULTS_DIR" --iteration "$ITERATION" \
  --wandb-project "$WANDB_PROJECT" --wandb-group "$WANDB_GROUP" \
  --wandb-run-name "${ITERATION}-gsm8k"
```