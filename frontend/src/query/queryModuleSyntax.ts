/**
 * Composes parameterized Cypher for a Query module from chained fragment nodes.
 * Fragments use `plan` after `WITH $plan AS plan` (see qf_start default).
 */

export const DEFAULT_MODULE_HEADER = `MATCH (c:Chunk)
WHERE true`;

export const DEFAULT_MODULE_FOOTER = `RETURN c.id AS chunkId, c.text AS preview
LIMIT coalesce($limit, 50)`;

/** Seeded defaults when a fragment is created; users edit per-node `data.cypherTemplate`. */
export const FRAGMENT_TEMPLATE_DEFAULTS: Record<string, string> = {
  qf_start: 'WITH $plan AS plan',
  qf_topic: `AND ANY(tag IN [t IN plan.tags WHERE t.facets.topic >= 0.5 | t.t] WHERE EXISTS((c)-[:HAS_TAG {facet: 'topic'}]->(:Tag {name: tag})))`,
  qf_entities: `AND ANY(tag IN [t IN plan.tags WHERE t.facets.entities >= 0.5 | t.t] WHERE EXISTS((c)-[:HAS_TAG {facet: 'entities'}]->(:Tag {name: tag})))`,
  qf_activity: `AND ANY(tag IN [t IN plan.tags WHERE t.facets.activity >= 0.5 | t.t] WHERE EXISTS((c)-[:HAS_TAG {facet: 'activity'}]->(:Tag {name: tag})))`,
  qf_temporal: `AND ANY(tag IN [t IN plan.tags WHERE t.facets.temporal >= 0.5 | t.t] WHERE EXISTS((c)-[:HAS_TAG {facet: 'temporal'}]->(:Tag {name: tag})))`,
  qf_evidence: `AND ANY(tag IN [t IN plan.tags WHERE t.facets.evidence >= 0.5 | t.t] WHERE EXISTS((c)-[:HAS_TAG {facet: 'evidence'}]->(:Tag {name: tag})))`,
};

/** Snippets for “insert at cursor” in the template editor (interpreter binds `$plan`). */
export const PLAN_INSERTS: { label: string; text: string }[] = [
  { label: 'WITH plan', text: 'WITH $plan AS plan' },
  { label: 'plan.tags', text: 'plan.tags' },
  { label: 'topic ≥ 0.5', text: "[t IN plan.tags WHERE t.facets.topic >= 0.5 | t.t]" },
  { label: 'entities ≥ 0.5', text: "[t IN plan.tags WHERE t.facets.entities >= 0.5 | t.t]" },
  { label: 'facet: topic', text: "[:HAS_TAG {facet: 'topic'}]" },
  { label: 'limit', text: '$limit' },
];

export const DEMO_PLAN_PREVIEW = {
  description: 'Q2 revenue trends and changes',
  tags: [
    { t: 'revenue_analysis', w_query: 0.72, facets: { topic: 0.9, entities: 0.1, activity: 0.3, temporal: 0.2, evidence: 0.3 } },
    { t: 'market_expansion',  w_query: 0.58, facets: { topic: 0.8, entities: 0.1, activity: 0.6, temporal: 0.1, evidence: 0.1 } },
    { t: 'q2_2025',           w_query: 0.50, facets: { topic: 0.1, entities: 0.0, activity: 0.1, temporal: 0.9, evidence: 0.1 } },
  ],
  filters: { dataset_id: null, limit: 20 },
};

/**
 * Default plain-language copy per fragment kind (shown when `humanNote` is empty).
 * Canvas chain order is the meaning order; this text is what builders read—not Cypher.
 */
export const FRAGMENT_HUMAN_DEFAULTS: Record<string, string> = {
  qf_start:
    'Receive the interpreter\'s structured plan and make it available as `plan` for the steps that follow.',
  qf_topic: 'Narrow to chunks whose tags match the topic focus the interpreter extracted for this question.',
  qf_entities: 'Keep chunks that mention the entities the plan singled out.',
  qf_activity: 'Filter by the kinds of events or processes that matter for this run.',
  qf_temporal: 'Apply the temporal relevance or status posture from the plan.',
  qf_evidence: 'Prefer chunks that supply the answer material the question needs.',
};

type FlowNode = {
  id: string;
  type?: string;
  parentId?: string;
  data?: {
    kind?: string;
    cypherTemplate?: string;
    headerCypher?: string;
    footerCypher?: string;
    /** Plain-language override for this fragment; empty → FRAGMENT_HUMAN_DEFAULTS[kind]. */
    humanNote?: string;
    /** Module-level intent in plain language (optional). */
    humanSummary?: string;
  };
};

type FlowEdge = { source: string; target: string };

export function orderFragmentChain(nodes: FlowNode[], edges: FlowEdge[], groupId: string): string[] {
  const inGroup = (id: string) => nodes.find((x) => x.id === id)?.parentId === groupId;
  const start = nodes.find((n) => n.parentId === groupId && n.data?.kind === 'qf_start');
  if (!start) return [];

  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!inGroup(e.source) || !inGroup(e.target)) continue;
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  }

  const order: string[] = [];
  let cur: string | undefined = start.id;
  const seen = new Set<string>();
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    order.push(cur);
    const nextId: string | undefined = adj.get(cur)?.[0];
    cur = nextId;
  }
  return order;
}

export function getFragmentTemplate(node: FlowNode | undefined, kind: string): string {
  const custom = node?.data?.cypherTemplate;
  if (typeof custom === 'string') return custom;
  return FRAGMENT_TEMPLATE_DEFAULTS[kind] ?? '';
}

/** Readable line for inspector + module story (custom note, else default blurb). */
export function getFragmentHumanLine(node: FlowNode | undefined, kind: string): string {
  const note = node?.data?.humanNote;
  if (typeof note === 'string' && note.trim()) return note.trim();
  return FRAGMENT_HUMAN_DEFAULTS[kind] ?? '';
}

export function composeHumanStory(
  nodes: FlowNode[],
  edges: FlowEdge[],
  groupId: string,
  stepTitle: (kind: string) => string,
): { steps: { id: string; kind: string; title: string; body: string }[]; warnings: string[] } {
  const ids = orderFragmentChain(nodes, edges, groupId);
  const warnings: string[] = [];
  if (!ids.length) warnings.push('Connect fragments from Start so the narrative follows your canvas order.');

  const steps: { id: string; kind: string; title: string; body: string }[] = [];
  for (const id of ids) {
    const node = nodes.find((n) => n.id === id);
    const kind = node?.data?.kind;
    if (!kind) continue;
    steps.push({
      id,
      kind,
      title: stepTitle(kind),
      body: getFragmentHumanLine(node, kind),
    });
  }
  return { steps, warnings };
}

export function composeModuleCypher(
  nodes: FlowNode[],
  edges: FlowEdge[],
  groupId: string,
): { text: string; chain: { id: string; kind: string }[]; warnings: string[] } {
  const group = nodes.find((n) => n.id === groupId && n.type === 'queryGroup');
  const header = (group?.data?.headerCypher ?? DEFAULT_MODULE_HEADER).trim();
  const footer = (group?.data?.footerCypher ?? DEFAULT_MODULE_FOOTER).trim();

  const ids = orderFragmentChain(nodes, edges, groupId);
  const warnings: string[] = [];
  if (!ids.length) warnings.push('No fragment chain starting from qf_start inside this module.');

  const chain: { id: string; kind: string }[] = [];
  const bodyParts: string[] = [];

  for (const id of ids) {
    const node = nodes.find((n) => n.id === id);
    const kind = node?.data?.kind;
    if (!kind) continue;
    chain.push({ id, kind });
    const tpl = getFragmentTemplate(node, kind).trim();
    if (tpl) bodyParts.push(tpl);
  }

  const body = bodyParts.join('\n');
  const text = [header, body, footer].filter(Boolean).join('\n\n');
  return { text, chain, warnings };
}

/** Rough list of plan fields referenced (for the inspector summary). */
export function extractPlanRefs(cypher: string): string[] {
  const re = /plan\.(\w+)/g;
  const out = new Set<string>();
  let m;
  while ((m = re.exec(cypher)) !== null) out.add(m[1]);
  return [...out].sort();
}
