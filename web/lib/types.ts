export type AskType = "answer" | "refuse" | "factsheet_only" | "error";

export type AskResponse = {
  type: AskType;
  text: string;
  citation_url: string;
  citation_label: string;
  last_updated_from_sources: string;
  disclaimer: string;
};

export type UserTurn = {
  id: string;
  role: "user";
  text: string;
};

export type AssistantTurn = {
  id: string;
  role: "assistant";
  response: AskResponse;
};

export type PendingTurn = {
  id: string;
  role: "pending";
  hint: string;
};

export type Turn = UserTurn | AssistantTurn | PendingTurn;
