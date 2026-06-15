/** Run frame (line 0) — static audit for every RAGAS export arm. */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

import {
  RAGAS_EXPORT_SCHEMA,
  buildCohortManifest,
  isRunFrameRow,
  type CohortManifest,
  type ExportArm,
  type GoldQuestion,
  type RunFrame,
  type RunFrameInvocation,
  type RunFrameResolved,
} from '../../src/rag/exportContract';
import { pipelinePromptsForFrame } from '../../src/rag/pipelinePrompts';
import { loadBuilderManifestPath } from './cohort';

export function readRunFrame(outPath: string): RunFrame | null {
  if (!existsSync(outPath)) return null;
  const first = readFileSync(outPath, 'utf-8').split('\n').find((l) => l.trim());
  if (!first) return null;
  try {
    const row = JSON.parse(first);
    return isRunFrameRow(row) ? row : null;
  } catch {
    return null;
  }
}

export function writeRunFrame(outPath: string, frame: RunFrame, fresh: boolean): void {
  if (fresh || !existsSync(outPath)) {
    writeFileSync(outPath, `${JSON.stringify(frame)}\n`, 'utf-8');
    return;
  }
  const existing = readRunFrame(outPath);
  if (!existing) {
    const body = readFileSync(outPath, 'utf-8');
    writeFileSync(outPath, `${JSON.stringify(frame)}\n${body}`, 'utf-8');
  }
}

export function buildRunFrame(opts: {
  arm: ExportArm;
  routeOrigin: string | null;
  label: string | null;
  invocation: RunFrameInvocation;
  resolved: RunFrameResolved;
  questionsPath: string;
  cohortItems: GoldQuestion[];
  configSource?: Record<string, unknown>;
  includePrompts?: boolean;
}): RunFrame {
  const builderManifest = loadBuilderManifestPath(opts.questionsPath);
  const cohort: CohortManifest = buildCohortManifest(
    opts.questionsPath,
    opts.cohortItems,
    builderManifest,
  );
  return {
    kind: 'run_frame',
    schema: RAGAS_EXPORT_SCHEMA,
    exported_at: new Date().toISOString(),
    arm: opts.arm,
    route_origin: opts.routeOrigin,
    label: opts.label,
    invocation: opts.invocation,
    resolved: opts.resolved,
    cohort,
    ...(opts.includePrompts !== false ? { prompts: pipelinePromptsForFrame() } : {}),
    ...(opts.configSource ? { config_source: opts.configSource } : {}),
  };
}
