import API from "@/utils/api";
import { CreateNoteRequest, UpdateNoteRequest } from "./types";
import { Note } from "@/types/note";

const APP_CONFIG_URL = "/api/note";

export const createNote = async (planId: string, data: CreateNoteRequest) => {
  const response = await API.post<Note>(
    `${APP_CONFIG_URL}?planId=${planId}`,
    data,
  );
  return response.data;
};

export const updateNote = async (noteId: string, data: UpdateNoteRequest) => {
  const response = await API.patch<Note>(`${APP_CONFIG_URL}/${noteId}`, data);
  return response.data;
};

export const deleteNote = async (noteId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${noteId}`);
  return response.data;
};
