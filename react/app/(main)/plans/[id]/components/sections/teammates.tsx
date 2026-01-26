"use client";

import { cn } from "@/lib/utils";
import { Participant } from "@/types/participant";
import { UserPlus } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import TeammateCard from "./teammate-card";
import InviteTeammateDialog from "./invite-teammate-dialog";
import {
  deleteParticipant,
  inviteTeammate,
} from "@/api/participant/participant";
import toast from "react-hot-toast";
import { useParams } from "next/navigation";
import {
  InvitationStatus,
  InviteTeammateRequest,
  PlanRole,
} from "@/api/participant/types";
import { User } from "@/types/user";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";

interface TeammatesProps {
  className?: string;
  participants: Participant[];
  onUpdate: (participants: Participant[]) => void;
}

const Teammates = forwardRef<HTMLDivElement, TeammatesProps>(function Teammates(
  { className, participants, onUpdate },
  ref,
) {
  const params = useParams();
  const planId = params.id as string;

  const [isInviteOpen, setIsInviteOpen] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editRole, setEditRole] = useState<PlanRole>(PlanRole.Viewer);

  // Delete modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [participantToDelete, setParticipantToDelete] =
    useState<Participant | null>(null);

  const editCardRef = useRef<HTMLDivElement>(null);

  const handleInvite = async (user: User, role: PlanRole) => {
    try {
      const newParticipant = await inviteTeammate(planId, {
        userId: user.id,
        role,
      } as InviteTeammateRequest);

      const participantWithUserInfo: Participant = {
        ...newParticipant,
        name: user.name,
        username: user.username,
        avatarUrl: user.avatarUrl,
      };

      const newParticipants = [...participants, participantWithUserInfo];
      onUpdate(newParticipants);
      toast.success("Sent Invitation");
    } catch (error) {
      console.error("Failed to invite teammate:", error);
      toast.error("Failed to send invitation.");
    }
  };

  const handleEditTeammate = (teammate: Participant) => {
    setEditingId(teammate.id);
    setEditRole(teammate.role);
  };

  const handleConfirmEdit = () => {
    if (editingId) {
      const updatedParticipants = participants.map((t) =>
        t.id === editingId ? { ...t, role: editRole } : t,
      );
      onUpdate(updatedParticipants);
    }
    handleCancelEdit();
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditRole(PlanRole.Viewer);
  };

  const handleDeleteTeammate = (participant: Participant) => {
    setParticipantToDelete(participant);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!participantToDelete) return;

    try {
      await deleteParticipant(participantToDelete.id);
      const updatedParticipants = participants.filter(
        (t) => t.id !== participantToDelete.id,
      );
      onUpdate(updatedParticipants);
      toast.success("Removed Participant");
    } catch (error) {
      console.error("Failed to delete participant:", error);
      toast.error("Failed to remove participant.");
    } finally {
      setParticipantToDelete(null);
    }
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
  const sortedTeammates = [...participants].sort((a, b) => {
    if (a.role === PlanRole.Owner) return -1;
    if (b.role === PlanRole.Owner) return 1;
    if (
      a.status === InvitationStatus.Accepted &&
      b.status === InvitationStatus.Pending
    )
      return -1;
    if (
      a.status === InvitationStatus.Pending &&
      b.status === InvitationStatus.Accepted
    )
      return 1;
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
        <h2 className="text-2xl font-bold text-gray-800">Participants</h2>

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => setIsInviteOpen(true)}
          disabled={editingId !== null}
        >
          <UserPlus size={16} strokeWidth={3} />
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
            onDelete={() => handleDeleteTeammate(teammate)}
            isOwner={teammate.role === PlanRole.Owner}
            containerRef={editCardRef}
          />
        ))}
      </div>

      <InviteTeammateDialog
        open={isInviteOpen}
        onOpenChange={setIsInviteOpen}
        onInvite={handleInvite}
        existingTeammateIds={participants.map((t) => t.userId)}
      />

      <ConfirmDeleteModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title="Remove Participant"
        description={`Are you sure you want to remove ${
          participantToDelete?.name
            ? `"${participantToDelete.name}" (${participantToDelete.username})`
            : `"${participantToDelete?.username}"`
        } from plan ?`}
        onConfirm={handleConfirmDelete}
      />
    </section>
  );
});

export default Teammates;
