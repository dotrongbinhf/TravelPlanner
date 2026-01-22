"use client";

import { cn } from "@/lib/utils";
import { Teammate, TeammateRole, User } from "@/types/teammate";
import { UserPlus } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import TeammateCard from "./teammate-card";
import InviteTeammateDialog from "./invite-teammate-dialog";

interface TeammatesProps {
  className?: string;
}

const Teammates = forwardRef<HTMLDivElement, TeammatesProps>(function Teammates(
  { className },
  ref,
) {
  const [teammates, setTeammates] = useState<Teammate[]>([
    {
      id: "owner-1",
      name: "John Doe",
      email: "john@example.com",
      role: "owner",
      status: "active",
    },
    {
      id: "t1",
      name: "Jane Smith",
      email: "jane@example.com",
      role: "editor",
      status: "active",
    },
    {
      id: "t2",
      name: "Mike Wilson",
      email: "mike@example.com",
      role: "viewer",
      status: "pending",
    },
  ]);

  const [isInviteOpen, setIsInviteOpen] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<TeammateRole>("viewer");
  const editCardRef = useRef<HTMLDivElement>(null);

  const handleInvite = (user: User, role: TeammateRole) => {
    const newTeammate: Teammate = {
      id: user.id,
      name: user.name,
      email: user.email,
      avatar: user.avatar,
      role,
      status: "pending",
    };
    setTeammates((prev) => [...prev, newTeammate]);
  };

  const handleEditTeammate = (teammate: Teammate) => {
    setEditingId(teammate.id);
    setEditRole(teammate.role);
  };

  const handleConfirmEdit = () => {
    if (editingId) {
      setTeammates((prev) =>
        prev.map((t) => (t.id === editingId ? { ...t, role: editRole } : t)),
      );
    }
    handleCancelEdit();
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditRole("viewer");
  };

  const handleDeleteTeammate = (teammateId: string) => {
    setTeammates((prev) => prev.filter((t) => t.id !== teammateId));
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        editingId &&
        editCardRef.current &&
        !editCardRef.current.contains(event.target as Node)
      ) {
        handleCancelEdit();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [editingId]);

  // Sort teammates: owner first, then by status (active before pending)
  const sortedTeammates = [...teammates].sort((a, b) => {
    if (a.role === "owner") return -1;
    if (b.role === "owner") return 1;
    if (a.status === "active" && b.status === "pending") return -1;
    if (a.status === "pending" && b.status === "active") return 1;
    return 0;
  });

  return (
    <section
      ref={ref}
      id="teammates"
      data-section-id="teammates"
      className={cn(className, "flex flex-col gap-4")}
    >
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Teammates</h2>

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => setIsInviteOpen(true)}
          disabled={editingId !== null}
        >
          <UserPlus size={16} />
          <span className="text-sm font-medium">Invite Teammate</span>
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {sortedTeammates.map((teammate) => (
          <TeammateCard
            key={teammate.id}
            teammate={teammate}
            isEditing={editingId === teammate.id}
            editRole={editRole}
            onRoleChange={setEditRole}
            onConfirm={handleConfirmEdit}
            onCancel={handleCancelEdit}
            onEdit={() => handleEditTeammate(teammate)}
            onDelete={() => handleDeleteTeammate(teammate.id)}
            isOwner={teammate.role === "owner"}
            containerRef={editCardRef}
          />
        ))}
      </div>

      <InviteTeammateDialog
        open={isInviteOpen}
        onOpenChange={setIsInviteOpen}
        onInvite={handleInvite}
        existingTeammateIds={teammates.map((t) => t.id)}
      />
    </section>
  );
});

export default Teammates;
