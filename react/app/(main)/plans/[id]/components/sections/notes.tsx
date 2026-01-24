"use client";

import { cn } from "@/lib/utils";
import { Note } from "@/types/note";
import { Plus } from "lucide-react";
import {
  Dispatch,
  forwardRef,
  SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import NoteCard from "./note-card";
import { createNote, deleteNote, updateNote } from "@/api/note/note";
import { CreateNoteRequest } from "@/api/note/types";
import toast from "react-hot-toast";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";

interface NotesProps {
  planId: string;
  notes: Note[];
  updateNotes: (notes: Note[]) => void;
}

const Notes = forwardRef<HTMLDivElement, NotesProps>(function Notes(
  { planId, notes, updateNotes },
  ref,
) {
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [noteToDelete, setNoteToDelete] = useState<Note | null>(null);

  const newNoteRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const editNoteRef = useRef<HTMLDivElement>(null);
  const editTitleInputRef = useRef<HTMLInputElement>(null);

  const handleAddNote = () => {
    setIsAdding(true);
    setNewTitle("");
    setNewContent("");
  };

  const handleConfirmAdd = async () => {
    if (newTitle.trim() || newContent.trim()) {
      const newCreateNoteRequest: CreateNoteRequest = {
        title: newTitle.trim() || "Untitled",
        content: newContent.trim(),
      };
      try {
        const newNote = await createNote(planId, newCreateNoteRequest);
        updateNotes([...notes, newNote]);
        toast.success("Created New Note");
      } catch (error) {
        console.error("Error creating note:", error);
        toast.error("Failed to create note");
      }
    }
    handleCancelAdd();
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewTitle("");
    setNewContent("");
  };

  const handleDeleteNote = (note: Note) => {
    setNoteToDelete(note);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!noteToDelete) return;
    try {
      await deleteNote(noteToDelete.id);
      updateNotes(notes.filter((note) => note.id !== noteToDelete.id));
      toast.success("Note deleted successfully");
    } catch (error) {
      console.error("Error deleting note:", error);
      toast.error("Failed to delete note");
    } finally {
      setNoteToDelete(null);
    }
  };

  const handleEditNote = (note: Note) => {
    setEditingId(note.id);
    setEditTitle(note.title);
    setEditContent(note.content);
  };

  const handleConfirmEdit = () => {
    if (editingId && (editTitle.trim() || editContent.trim())) {
      try {
        updateNote(editingId, {
          title: editTitle.trim() || "Untitled",
          content: editContent.trim(),
        });
        toast.success("Updated Note");
      } catch (error) {
        console.error("Error updating note:", error);
        toast.error("Failed to update note");
      }
      updateNotes(
        notes.map((note) =>
          note.id === editingId
            ? {
                ...note,
                title: editTitle.trim() || "Untitled",
                content: editContent.trim(),
              }
            : note,
        ),
      );
    }
    handleCancelEdit();
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditTitle("");
    setEditContent("");
  };

  useEffect(() => {
    if (isAdding && titleInputRef.current) {
      titleInputRef.current.focus();
    }
  }, [isAdding]);

  useEffect(() => {
    if (editingId && editTitleInputRef.current) {
      editTitleInputRef.current.focus();
    }
  }, [editingId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isAdding &&
        newNoteRef.current &&
        !newNoteRef.current.contains(event.target as Node)
      ) {
        handleCancelAdd();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isAdding]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        editingId &&
        editNoteRef.current &&
        !editNoteRef.current.contains(event.target as Node)
      ) {
        handleCancelEdit();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [editingId]);

  return (
    <section
      ref={ref}
      id="notes"
      data-section-id="notes"
      className="flex flex-col gap-4"
    >
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Notes</h2>

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleAddNote}
          disabled={isAdding || editingId !== null}
        >
          <Plus size={16} strokeWidth={3} />
          <span className="text-sm font-medium">Add a note</span>
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {notes.map((note) => (
          <NoteCard
            key={note.id}
            note={note}
            isEditing={editingId === note.id}
            title={editTitle}
            content={editContent}
            onTitleChange={setEditTitle}
            onContentChange={setEditContent}
            onConfirm={handleConfirmEdit}
            onCancel={handleCancelEdit}
            onEdit={() => handleEditNote(note)}
            onDelete={() => handleDeleteNote(note)}
            titleInputRef={editTitleInputRef}
            containerRef={editNoteRef}
          />
        ))}

        {isAdding && (
          <NoteCard
            isEditing={true}
            title={newTitle}
            content={newContent}
            onTitleChange={setNewTitle}
            onContentChange={setNewContent}
            onConfirm={handleConfirmAdd}
            onCancel={handleCancelAdd}
            titleInputRef={titleInputRef}
            containerRef={newNoteRef}
          />
        )}
      </div>

      <ConfirmDeleteModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title="Delete Note"
        description={`Are you sure you want to delete "${noteToDelete?.title || "this note"}" ? This action cannot be undone !`}
        onConfirm={handleConfirmDelete}
      />
    </section>
  );
});

export default Notes;
