"use client";

import { cn } from "@/lib/utils";
import { Note } from "@/types/note";
import { CirclePlus } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import NoteCard from "./note-card";

interface NotesProps {
  className?: string;
}

const Notes = forwardRef<HTMLDivElement, NotesProps>(function Notes(
  { className },
  ref,
) {
  const [notes, setNotes] = useState<Note[]>([
    {
      id: "1",
      title: "Emergency Contact",
      content:
        "Remember to contact the local embassy in case of any emergencies.",
    },
    {
      id: "2",
      title: "Hotel Info",
      content: "Check-in at 2PM. Front desk is available 24/7.",
    },
  ]);

  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");

  const newNoteRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const editNoteRef = useRef<HTMLDivElement>(null);
  const editTitleInputRef = useRef<HTMLInputElement>(null);

  const handleAddNote = () => {
    setIsAdding(true);
    setNewTitle("");
    setNewContent("");
  };

  const handleConfirmAdd = () => {
    if (newTitle.trim() || newContent.trim()) {
      const newNote: Note = {
        id: Date.now().toString(),
        title: newTitle.trim() || "Untitled",
        content: newContent.trim(),
      };
      setNotes((prev) => [...prev, newNote]);
    }
    handleCancelAdd();
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewTitle("");
    setNewContent("");
  };

  const handleDeleteNote = (noteId: string) => {
    setNotes((prev) => prev.filter((note) => note.id !== noteId));
  };

  const handleEditNote = (note: Note) => {
    setEditingId(note.id);
    setEditTitle(note.title);
    setEditContent(note.content);
  };

  const handleConfirmEdit = () => {
    if (editingId && (editTitle.trim() || editContent.trim())) {
      setNotes((prev) =>
        prev.map((note) =>
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
      className={cn(className, "flex flex-col gap-4")}
    >
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Notes</h2>

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleAddNote}
          disabled={isAdding || editingId !== null}
        >
          <CirclePlus size={16} />
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
            onDelete={() => handleDeleteNote(note.id)}
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
    </section>
  );
});

export default Notes;
