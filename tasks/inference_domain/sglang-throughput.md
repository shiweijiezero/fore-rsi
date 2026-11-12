# Improve SGLang throughput

## Objective

Improve the throughput of the SGLang service for the project's representative workload while preserving its answer-quality and latency requirements. Deliver a recommended configuration, measurements, and any code changes needed to reproduce the result.

## Environment and budget

Use the SGLang checkout, model, workload, and GPU environment available to this task. Read the project's deployment and benchmark instructions to identify the service entry point and the existing quality and latency requirements. Resolve missing access or workload requirements with the Coordinator before running experiments.

Spend at most two hours on exploration, implementation, and verification. Reuse the available images, dependencies, and caches. Coordinate use of shared GPUs so concurrent experiments do not distort measurements.

## Team

- 4 Explorers investigate bottlenecks, compare approaches, and propose experiments.
- 4 Workers implement and measure the selected approaches.
- 2 Verifiers independently check the results against the objective and constraints.
- Other roles use the workflow's defaults.

## Work

Measure the current service with the representative workload before making changes. Use comparable model, hardware, request, and concurrency settings when evaluating candidates. Record completed requests per second, latency, errors, and the project's answer-quality results.

Prioritize changes supported by the measurements. Keep promising changes separate until their individual effects are understood, then verify combinations that could improve the result. Retain only improvements that meet the quality and latency requirements.

## Deliverables

Provide the recommended configuration and code changes, the commands needed to reproduce the measurements, and a comparison with the original service. Explain the measured benefit and any trade-offs that affect deployment. If no candidate improves throughput within the constraints, report that result and the most useful findings.

Stop within the time budget, release resources created for the experiments, and preserve the results and runnable changes.
