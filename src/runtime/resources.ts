// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Defines compute and network resource requirements for tasks.
 * ResourceConstraints describes the limits for an allocation. Resource combines
 * per-machine, per-workload and concurrent-total scopes into one task declaration.
 */
import Type from "typebox";

/** Resource limits for one accounting scope; null preserves the enclosing limits. */
export const ResourceConstraintsSchema = Type.Object({
  maxGpuNodes: Type.Union([Type.Integer({ minimum: 0 }), Type.Null()], {
    description: "Maximum number of hosts actually using GPUs.",
  }),
  gpu: Type.Object({
    maxCount: Type.Union([Type.Integer({ minimum: 0 }), Type.Null()], {
      description: "Maximum total number of whole GPUs; null adds no limit.",
    }),
    types: Type.Union([
      Type.Array(Type.Object({
        machines: Type.Optional(Type.Array(Type.String())),
        vendor: Type.Optional(Type.String()),
        model: Type.Optional(Type.String()),
        maxCount: Type.Union([Type.Integer({ minimum: 0 }), Type.Null()], {
          description: "Maximum total GPUs matching this entry; null adds no limit.",
        }),
      })),
      Type.Null(),
    ], {
      description: "Allowed GPU selectors. Null adds no restriction; an empty list allows no GPUs. Conditions within an entry intersect, and every matching count limit applies without counting a device twice.",
    }),
  }),
  maxCpuCores: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
    description: "Maximum total CPU cores; fractional cores are allowed.",
  }),
  maxHostMemory: Type.Union([
    Type.Number({ minimum: 0 }),
    Type.String(),
    Type.Null(),
  ], {
    description: "Maximum total host memory. Numbers use GB; strings may include a unit; null adds no limit.",
  }),
  network: Type.Union([
    Type.Object({
      requireRdma: Type.Boolean({
        description: "Whether data communication must use RDMA; false permits automatic selection.",
      }),
      interfaces: Type.Union([
        Type.Array(Type.Object({
          machines: Type.Optional(Type.Array(Type.String())),
          names: Type.Optional(Type.Array(Type.String())),
          vendor: Type.Optional(Type.String()),
          model: Type.Optional(Type.String()),
          minLinkSpeedGbps: Type.Optional(Type.Number({
            minimum: 0,
            description: "Minimum negotiated interface speed in Gb/s, not reserved bandwidth.",
          })),
        })),
        Type.Null(),
      ], {
        description: "Conditions within one selector intersect; selectors form an allowed union. Null adds no restriction; an empty list allows no data interfaces.",
      }),
    }),
    Type.Null(),
  ], {
    description: "Data-network requirements; null permits automatic selection within the enclosing limits.",
  }),
});

/** Task resource settings, combining machine, workload and concurrent-total limits. */
export const ResourceSchema = Type.Object({
  machineConstraints: Type.Union([
    Type.Record(
      Type.String(),
      Type.Omit(ResourceConstraintsSchema, ["maxGpuNodes"]),
    ),
    Type.Null(),
  ], {
    description: "Per-machine concurrent limits. Null uses the host's authorized scope; an empty map allows no machines.",
  }),
  perExecutionConstraints: Type.With(ResourceConstraintsSchema, {
    description: "Limits for one complete workload, including its cross-machine jobs and supporting services, rather than each shell command.",
  }),
  totalExecutionConstraints: Type.With(ResourceConstraintsSchema, {
    description: "Concurrent totals across all managed executions, including preparation and jobs or services whose resources remain allocated.",
  }),
  resourceComments: Type.Array(Type.String()),
});

export const GpuConstraintsSchema = ResourceConstraintsSchema.properties.gpu;
export const NetworkConstraintsSchema = Type.Exclude(ResourceConstraintsSchema.properties.network, Type.Null());

export type Resource = Type.Static<typeof ResourceSchema>;
export type ResourceConstraints = Type.Static<typeof ResourceConstraintsSchema>;
export type GpuConstraints = Type.Static<typeof GpuConstraintsSchema>;
export type NetworkConstraints = Type.Static<typeof NetworkConstraintsSchema>;
