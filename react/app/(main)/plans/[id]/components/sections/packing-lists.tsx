"use client";

import { cn } from "@/lib/utils";
import { PackingList } from "@/types/packing-list";
import { CirclePlus } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import PackingListCard from "./packing-list-card";

interface PackingListsProps {
  className?: string;
}

const PackingLists = forwardRef<HTMLDivElement, PackingListsProps>(
  function PackingLists({ className }, ref) {
    const [lists, setLists] = useState<PackingList[]>([
      {
        id: "1",
        name: "Clothes",
        items: [
          { id: "1-1", name: "T-shirts", checked: true },
          { id: "1-2", name: "Jeans", checked: false },
          { id: "1-3", name: "Jacket", checked: false },
        ],
      },
      {
        id: "2",
        name: "Electronics",
        items: [
          { id: "2-1", name: "Phone charger", checked: true },
          { id: "2-2", name: "Laptop", checked: false },
        ],
      },
    ]);

    const [isAdding, setIsAdding] = useState(false);
    const [newName, setNewName] = useState("");

    const [editingId, setEditingId] = useState<string | null>(null);
    const [editName, setEditName] = useState("");

    const newListRef = useRef<HTMLDivElement>(null);
    const nameInputRef = useRef<HTMLInputElement>(null);
    const editListRef = useRef<HTMLDivElement>(null);
    const editNameInputRef = useRef<HTMLInputElement>(null);

    const handleAddList = () => {
      setIsAdding(true);
      setNewName("");
    };

    const handleConfirmAdd = () => {
      if (newName.trim()) {
        const newList: PackingList = {
          id: Date.now().toString(),
          name: newName.trim(),
          items: [],
        };
        setLists((prev) => [...prev, newList]);
      }
      handleCancelAdd();
    };

    const handleCancelAdd = () => {
      setIsAdding(false);
      setNewName("");
    };

    const handleDeleteList = (listId: string) => {
      setLists((prev) => prev.filter((list) => list.id !== listId));
    };

    const handleEditList = (list: PackingList) => {
      setEditingId(list.id);
      setEditName(list.name);
    };

    const handleConfirmEdit = () => {
      if (editingId && editName.trim()) {
        setLists((prev) =>
          prev.map((list) =>
            list.id === editingId ? { ...list, name: editName.trim() } : list,
          ),
        );
      }
      handleCancelEdit();
    };

    const handleCancelEdit = () => {
      setEditingId(null);
      setEditName("");
    };

    const handleToggleItem = (listId: string, itemId: string) => {
      setLists((prev) =>
        prev.map((list) =>
          list.id === listId
            ? {
                ...list,
                items: list.items.map((item) =>
                  item.id === itemId
                    ? { ...item, checked: !item.checked }
                    : item,
                ),
              }
            : list,
        ),
      );
    };

    const handleAddItem = (listId: string, itemName: string) => {
      setLists((prev) =>
        prev.map((list) =>
          list.id === listId
            ? {
                ...list,
                items: [
                  ...list.items,
                  {
                    id: `${listId}-${Date.now()}`,
                    name: itemName,
                    checked: false,
                  },
                ],
              }
            : list,
        ),
      );
    };

    const handleEditItem = (
      listId: string,
      itemId: string,
      newName: string,
    ) => {
      setLists((prev) =>
        prev.map((list) =>
          list.id === listId
            ? {
                ...list,
                items: list.items.map((item) =>
                  item.id === itemId ? { ...item, name: newName } : item,
                ),
              }
            : list,
        ),
      );
    };

    const handleDeleteItem = (listId: string, itemId: string) => {
      setLists((prev) =>
        prev.map((list) =>
          list.id === listId
            ? {
                ...list,
                items: list.items.filter((item) => item.id !== itemId),
              }
            : list,
        ),
      );
    };

    useEffect(() => {
      if (isAdding && nameInputRef.current) {
        nameInputRef.current.focus();
      }
    }, [isAdding]);

    useEffect(() => {
      if (editingId && editNameInputRef.current) {
        editNameInputRef.current.focus();
      }
    }, [editingId]);

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (
          isAdding &&
          newListRef.current &&
          !newListRef.current.contains(event.target as Node)
        ) {
          handleCancelAdd();
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }, [isAdding]);

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (
          editingId &&
          editListRef.current &&
          !editListRef.current.contains(event.target as Node)
        ) {
          handleCancelEdit();
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }, [editingId]);

    return (
      <section
        ref={ref}
        id="packing-lists"
        data-section-id="packing-lists"
        className={cn(className, "flex flex-col gap-4")}
      >
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-800">Packing Lists</h2>

          <button
            className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleAddList}
            disabled={isAdding || editingId !== null}
          >
            <CirclePlus size={16} />
            <span className="text-sm font-medium">Add a list</span>
          </button>
        </div>

        <div className="flex flex-col gap-4">
          {lists.map((list) => (
            <PackingListCard
              key={list.id}
              list={list}
              isEditing={editingId === list.id}
              name={editName}
              onNameChange={setEditName}
              onConfirm={handleConfirmEdit}
              onCancel={handleCancelEdit}
              onEdit={() => handleEditList(list)}
              onDelete={() => handleDeleteList(list.id)}
              onToggleItem={(itemId) => handleToggleItem(list.id, itemId)}
              onAddItem={(itemName) => handleAddItem(list.id, itemName)}
              onEditItem={(itemId, newName) =>
                handleEditItem(list.id, itemId, newName)
              }
              onDeleteItem={(itemId) => handleDeleteItem(list.id, itemId)}
              nameInputRef={editNameInputRef}
              containerRef={editListRef}
            />
          ))}

          {isAdding && (
            <PackingListCard
              isEditing={true}
              name={newName}
              onNameChange={setNewName}
              onConfirm={handleConfirmAdd}
              onCancel={handleCancelAdd}
              nameInputRef={nameInputRef}
              containerRef={newListRef}
            />
          )}
        </div>
      </section>
    );
  },
);

export default PackingLists;
