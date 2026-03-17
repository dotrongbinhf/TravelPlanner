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

export type Message = {
  id: string;
  conversationId: string;
  content: string;
  messageRole: MessageRole;
  createdAt: string;
};

export type CreateMessageRequest = {
  conversationId: string;
  content: string;
  messageRole?: MessageRole;
};

// Agent streaming event types (received via SignalR from .NET → FastAPI)
export type AgentEvent = {
  eventType:
    | "agent_start"
    | "agent_end"
    | "tool_start"
    | "tool_end"
    | "text_chunk"
    | "workflow_complete"
    | "error";
  agentName?: string;
  content?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: Record<string, unknown>;
  outputSummary?: string;
  finalResponse?: string;
  errorMessage?: string;
  timestamp?: string;
};

export type AgentStreamState = {
  events: AgentEvent[];
  currentAgent: string | null;
  streamedContent: string;
  isComplete: boolean;
  error: string | null;
};
