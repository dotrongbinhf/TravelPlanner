"use client";

import { cn } from "@/lib/utils";
import { PackingList } from "@/types/packingList";
import { Plus } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import PackingListCard from "./packing-list-card";
import {
  createPackingList,
  deletePackingList,
  updatePackingList,
} from "@/api/packinglist/packinglist";
import {
  createPackingItem,
  deletePackingItem,
  updatePackingItem,
} from "@/api/packingItem/packingItem";
import toast from "react-hot-toast";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { PackingItem } from "@/types/packingItem";

interface PackingListsProps {
  className?: string;
  planId: string;
  packingLists: PackingList[];
  updatePackingLists: (packingLists: PackingList[]) => void;
}

const PackingLists = forwardRef<HTMLDivElement, PackingListsProps>(
  function PackingLists(
    { className, planId, packingLists, updatePackingLists },
    ref,
  ) {
    const [isAdding, setIsAdding] = useState(false);
    const [newName, setNewName] = useState("");

    const [editingId, setEditingId] = useState<string | null>(null);
    const [editName, setEditName] = useState("");

    // Delete confirmation modal state for packing list
    const [deleteModalOpen, setDeleteModalOpen] = useState(false);
    const [listToDelete, setListToDelete] = useState<PackingList | null>(null);

    // Delete confirmation modal state for packing item
    const [deleteItemModalOpen, setDeleteItemModalOpen] = useState(false);
    const [itemToDelete, setItemToDelete] = useState<{
      listId: string;
      item: PackingItem;
    } | null>(null);

    const newListRef = useRef<HTMLDivElement>(null);
    const nameInputRef = useRef<HTMLInputElement>(null);
    const editListRef = useRef<HTMLDivElement>(null);
    const editNameInputRef = useRef<HTMLInputElement>(null);

    const handleAddList = () => {
      setIsAdding(true);
      setNewName("");
    };

    const handleConfirmAdd = async () => {
      if (newName.trim()) {
        try {
          const newList = await createPackingList(planId, {
            name: newName.trim(),
          });
          updatePackingLists([...packingLists, newList]);
          toast.success("Created New Packing List");
        } catch (error) {
          console.error("Error creating packing list:", error);
          toast.error("Failed to create packing list");
        }
      }
      handleCancelAdd();
    };

    const handleCancelAdd = () => {
      setIsAdding(false);
      setNewName("");
    };

    const handleDeleteList = (list: PackingList) => {
      setListToDelete(list);
      setDeleteModalOpen(true);
    };

    const handleConfirmDelete = async () => {
      if (!listToDelete) return;
      try {
        await deletePackingList(listToDelete.id);
        updatePackingLists(
          packingLists.filter((list) => list.id !== listToDelete.id),
        );
        toast.success("Deleted Packing List");
      } catch (error) {
        console.error("Error deleting packing list:", error);
        toast.error("Failed to delete packing list");
      } finally {
        setListToDelete(null);
      }
    };

    const handleEditList = (list: PackingList) => {
      setEditingId(list.id);
      setEditName(list.name);
    };

    const handleConfirmEdit = async () => {
      if (editingId && editName.trim()) {
        try {
          await updatePackingList(editingId, { name: editName.trim() });
          updatePackingLists(
            packingLists.map((list) =>
              list.id === editingId ? { ...list, name: editName.trim() } : list,
            ),
          );
          toast.success("Updated Packing List");
        } catch (error) {
          console.error("Error updating packing list:", error);
          toast.error("Failed to update packing list");
        }
      }
      handleCancelEdit();
    };

    const handleCancelEdit = () => {
      setEditingId(null);
      setEditName("");
    };

    // Item handlers with API calls
    const handleToggleItem = async (listId: string, itemId: string) => {
      const list = packingLists.find((l) => l.id === listId);
      const item = list?.packingItems?.find((i) => i.id === itemId);
      if (!item) return;

      try {
        await updatePackingItem(itemId, {
          name: item.name,
          isPacked: !item.isPacked,
        });
        updatePackingLists(
          packingLists.map((list) =>
            list.id === listId
              ? {
                  ...list,
                  packingItems: list.packingItems.map((i) =>
                    i.id === itemId ? { ...i, isPacked: !i.isPacked } : i,
                  ),
                }
              : list,
          ),
        );
        toast.success(item.isPacked ? "Unpacked Item" : "Packed Item");
      } catch (error) {
        console.error("Error toggling packing item:", error);
        toast.error("Failed to update packing item");
      }
    };

    const handleAddItem = async (listId: string, itemName: string) => {
      try {
        const newItem = await createPackingItem(listId, {
          name: itemName.trim(),
        });
        updatePackingLists(
          packingLists.map((list) =>
            list.id === listId
              ? {
                  ...list,
                  packingItems: [...(list.packingItems || []), newItem],
                }
              : list,
          ),
        );
        toast.success("Created New Packing Item");
      } catch (error) {
        console.error("Error creating packing item:", error);
        toast.error("Failed to create packing item");
      }
    };

    const handleEditItem = async (
      listId: string,
      itemId: string,
      newName: string,
    ) => {
      const list = packingLists.find((l) => l.id === listId);
      const item = list?.packingItems?.find((i) => i.id === itemId);
      if (!item) return;

      try {
        await updatePackingItem(itemId, {
          name: newName.trim(),
          isPacked: item.isPacked,
        });
        updatePackingLists(
          packingLists.map((list) =>
            list.id === listId
              ? {
                  ...list,
                  packingItems: list.packingItems.map((i) =>
                    i.id === itemId ? { ...i, name: newName.trim() } : i,
                  ),
                }
              : list,
          ),
        );
        toast.success("Updated Packing Item");
      } catch (error) {
        console.error("Error updating packing item:", error);
        toast.error("Failed to update packing item");
      }
    };

    const handleDeleteItem = (listId: string, item: PackingItem) => {
      setItemToDelete({ listId, item });
      setDeleteItemModalOpen(true);
    };

    const handleConfirmDeleteItem = async () => {
      if (!itemToDelete) return;
      try {
        await deletePackingItem(itemToDelete.item.id);
        updatePackingLists(
          packingLists.map((list) =>
            list.id === itemToDelete.listId
              ? {
                  ...list,
                  packingItems: list.packingItems.filter(
                    (i) => i.id !== itemToDelete.item.id,
                  ),
                }
              : list,
          ),
        );
        toast.success("Deleted Packing Item");
      } catch (error) {
        console.error("Error deleting packing item:", error);
        toast.error("Failed to delete packing item");
      } finally {
        setItemToDelete(null);
      }
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
            <Plus size={16} strokeWidth={3} />
            <span className="text-sm font-medium">Add a list</span>
          </button>
        </div>

        <div className="flex flex-col gap-4">
          {packingLists.map((packingList) => (
            <PackingListCard
              key={packingList.id}
              list={packingList}
              isEditing={editingId === packingList.id}
              name={editName}
              onNameChange={setEditName}
              onConfirm={handleConfirmEdit}
              onCancel={handleCancelEdit}
              onEdit={() => handleEditList(packingList)}
              onDelete={() => handleDeleteList(packingList)}
              onToggleItem={(itemId) =>
                handleToggleItem(packingList.id, itemId)
              }
              onAddItem={(itemName) => handleAddItem(packingList.id, itemName)}
              onEditItem={(itemId, newName) =>
                handleEditItem(packingList.id, itemId, newName)
              }
              onDeleteItem={(item) => handleDeleteItem(packingList.id, item)}
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

        <ConfirmDeleteModal
          open={deleteModalOpen}
          onOpenChange={setDeleteModalOpen}
          title="Delete Packing List"
          description={`Are you sure you want to delete "${listToDelete?.name || "this list"}" ? This action cannot be undone !`}
          onConfirm={handleConfirmDelete}
        />

        <ConfirmDeleteModal
          open={deleteItemModalOpen}
          onOpenChange={setDeleteItemModalOpen}
          title="Delete Packing Item"
          description={`Are you sure you want to delete "${itemToDelete?.item.name || "this item"}" ? This action cannot be undone !`}
          onConfirm={handleConfirmDeleteItem}
        />
      </section>
    );
  },
);

export default PackingLists;
