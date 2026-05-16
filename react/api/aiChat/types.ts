export type Conversation = {
  id: string;
  planId: string;
  title: string;
  createdAt: string;
  updatedAt?: string;
};

export type CreateConversationRequest = {
  planId: string;
  title?: string;
};

export type UpdateConversationTitleRequest = {
  title: string;
};

export enum MessageRole {
  User = 0,
  Assistant = 1,
  System = 2,
}

export enum ApplyScope {
  OnlyChanges = 0,
  FullPlan = 1,
}

export type Message = {
  id: string;
  conversationId: string;
  content: string;
  messageRole: MessageRole;
  createdAt: string;
  generatedPlanData?: string | null;
  applyGeneratedPlanAt?: string | null;
};

export type CreateMessageRequest = {
  conversationId: string;
  content: string;
  messageRole?: MessageRole;
  generatedPlanData?: string;
};



// Agent streaming event types (received via SSE from .NET → FastAPI)
export type AgentEvent = {
  eventType:
    | "agent_start"
    | "agent_end"
    | "tool_start"
    | "tool_end"
    | "text_chunk"
    | "structured_data"
    | "workflow_complete"
    | "message_saved"
    | "error";
  agentName?: string;
  content?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: Record<string, unknown>;
  outputSummary?: string;
  finalResponse?: string;
  structuredData?: Record<string, unknown>;
  errorMessage?: string;
  messageId?: string;
  timestamp?: string;
};

export type AgentStreamState = {
  events: AgentEvent[];
  activeAgents: string[];
  completedAgents: string[];
  streamedContent: string;
  structuredData: Record<string, unknown> | null;
  isComplete: boolean;
  error: string | null;
  savedMessageId: string | null;
};
