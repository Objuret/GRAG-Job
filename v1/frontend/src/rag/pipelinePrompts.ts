/** LLM instruction text shared by live pipeline + RAGAS run_frame audit. */

export const GATE_SECTIONS = [
  'slack', 'documents', 'meeting_transcripts', 'meeting_chats', 'prs',
  'urls', 'answerable_questions', 'unanswerable_questions', 'product_profile',
] as const;

export const DEFAULT_ANSWER_JOB = {
  mode: 'direct_answer',
  evidence_policy: 'retrieved_only',
  missing_evidence_policy: 'say_insufficient_evidence',
} as const;

export function interpretPass1SystemPrompt(): string {
  return (
    'You interpret a user query for graph retrieval. Work in two steps. ' +
    'STEP 1: write "description" — a concise, self-contained 1–3 sentence statement of the ' +
    'underlying information need (what the user actually wants to find, including implied entities/scope), ' +
    'in plain declarative prose, not a restatement of the question. ' +
    'STEP 2: derive "tags" FROM that description — specific noun phrases, named entities, systems, or actions. ' +
    'No generic filler words. ' +
    'STEP 3: extract "gate" — hard structured constraints ONLY when the query explicitly names them, else null/[]. ' +
    'Fields: product (a "*Force"/"*Genie"-style product name if named), ' +
    `section (one of: ${GATE_SECTIONS.join(', ')} — map synonyms, e.g. "pull requests"->prs, "chat"->slack), ` +
    'channel (a Slack channel name if given), employee_id (an "eid_..." id if given), ' +
    'years (array of 4-digit years explicitly mentioned). ' +
    'Do NOT guess values that are not in the query. ' +
    'Return ONLY valid JSON: {"description":"...","tags":["tag1"],"gate":{"product":null,"section":null,"channel":null,"employee_id":null,"years":[]}}.'
  );
}

export function interpretPass2SystemPrompt(): string {
  return (
    'Score retrieval tags against five facets (each 0.0–1.0). ' +
    'topic: subject matter. entities: named people/orgs/products/systems. ' +
    'activity: events/processes/actions. temporal: time relevance. evidence: answer material type. ' +
    'Return ONLY valid JSON: {"scores":[{"t":"tag","facets":{"topic":0.0,"entities":0.0,"activity":0.0,"temporal":0.0,"evidence":0.0}}]}'
  );
}

export function answerSystemPrompt(
  evidencePolicy: string = DEFAULT_ANSWER_JOB.evidence_policy,
  missingPolicy: string = DEFAULT_ANSWER_JOB.missing_evidence_policy,
): string {
  return (
    `You are a retrieval-augmented assistant. Answer using only the provided chunks.\n` +
    `Evidence policy: ${evidencePolicy}.\n` +
    `If evidence is insufficient: ${missingPolicy}.\n` +
    `Cite chunks by their id number in brackets, e.g. [1] or [2,4].`
  );
}

export function pipelinePromptsForFrame(): Record<string, unknown> {
  return {
    interpret_pass1_system: interpretPass1SystemPrompt(),
    interpret_pass2_system: interpretPass2SystemPrompt(),
    answer_system: answerSystemPrompt(),
    answer_job: DEFAULT_ANSWER_JOB,
    answer_modes: {
      raw: 'user prompt only — no system framing or retrieved evidence',
      context: 'system policy + single user turn with formatted chunks',
      hybrid: 'system policy + raw prompt turn + evidence turn',
    },
    sql_agent: {
      note: 'SQL arm system prompt is built per run from live SQLite schema; see meta.sql_system on first row or backend/baselines/sql_agent.py SYSTEM_PROMPT_TEMPLATE.',
    },
  };
}
