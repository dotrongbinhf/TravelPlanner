import API from "@/utils/api";
import {
  Conversation,
  CreateConversationRequest,
  UpdateConversationTitleRequest,
  Message,
  CreateMessageRequest,
} from "./types";

const APP_CONFIG_URL = "/api/aichat";

export const getConversationsByPlanId = async (planId: string) => {
  const response = await API.get<Conversation[]>(
    `${APP_CONFIG_URL}/plans/${planId}/conversations`,
  );
  return response.data;
};

export const createConversation = async (
  planId: string,
  data: CreateConversationRequest,
) => {
  const response = await API.post<Conversation>(
    `${APP_CONFIG_URL}/plans/${planId}/conversations`,
    data,
  );
  return response.data;
};

export const updateConversationTitle = async (
  conversationId: string,
  data: UpdateConversationTitleRequest,
) => {
  const response = await API.put<Conversation>(
    `${APP_CONFIG_URL}/conversations/${conversationId}/title`,
    data,
  );
  return response.data;
};

export const getMessagesByConversationId = async (conversationId: string) => {
  const response = await API.get<Message[]>(
    `${APP_CONFIG_URL}/conversations/${conversationId}/messages`,
  );
  return response.data;
};

export const addMessage = async (
  conversationId: string,
  data: CreateMessageRequest,
) => {
  const response = await API.post<Message>(
    `${APP_CONFIG_URL}/conversations/${conversationId}/messages`,
    data,
  );
  return response.data;
};

export const deleteConversation = async (conversationId: string) => {
  const response = await API.delete(
    `${APP_CONFIG_URL}/conversations/${conversationId}`
  );
  return response.data;
};

export const markMessageApplied = async (messageId: string) => {
  const response = await API.patch<Message>(
    `${APP_CONFIG_URL}/messages/${messageId}/applied`
  );
  return response.data;
};
