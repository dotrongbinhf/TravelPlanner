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
