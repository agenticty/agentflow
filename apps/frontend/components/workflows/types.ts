export type AgentKind = "research" | "qualify" | "outreach";
export type JsonMap = Record<string, unknown>;

export type Step = {
  id: string;
  agent: AgentKind;
  instructions: string;
  input_map: JsonMap;
};
