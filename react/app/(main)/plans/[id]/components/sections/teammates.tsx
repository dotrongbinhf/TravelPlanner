"use client";

import { cn } from "@/lib/utils";
import { Collaborator } from "@/types/collaborator";
import { forwardRef } from "react";
import CollaboratorCard from "./teammate-card";
import {
  InvitationStatus,
  PlanRole,
} from "@/api/collaborator/types";
import { Plus } from "lucide-react";
import { useState } from "react";
import InviteTeammateDialog from "./invite-teammate-dialog";
import { inviteCollaborator, deleteCollaborator } from "@/api/collaborator/collaborator";
import { User } from "@/types/user";
import toast from "react-hot-toast";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";

interface SharingProps {
  className?: string;
  planId: string;
  isOwner: boolean;
  collaborators: Collaborator[];
  updateCollaborators: (collaborators: Collaborator[]) => void;
}

const Sharing = forwardRef<HTMLDivElement, SharingProps>(function Sharing(
  { className, planId, isOwner, collaborators, updateCollaborators },
  ref,
) {
  const [isInviteOpen, setIsInviteOpen] = useState(false);

  const handleInvite = async (user: User, role: PlanRole) => {
    try {
      const newCollaborator = await inviteCollaborator(planId, {
        userId: user.id,
        role: role,
      });

      // Update local state with the new collaborator
      const updatedCollaborators = [...collaborators, newCollaborator];
      updateCollaborators(updatedCollaborators);
      toast.success("Invitation sent successfully!");
    } catch (error: any) {
      toast.error(error?.response?.data || "Failed to invite collaborator");
    }
  };

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [collaboratorToDelete, setCollaboratorToDelete] = useState<Collaborator | null>(null);

  const handleDeleteClick = (collaborator: Collaborator) => {
    setCollaboratorToDelete(collaborator);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!collaboratorToDelete) return;

    try {
      await deleteCollaborator(collaboratorToDelete.id);
      
      const updatedCollaborators = collaborators.filter(
        (c) => c.id !== collaboratorToDelete.id
      );
      updateCollaborators(updatedCollaborators);
      toast.success("Member removed successfully!");
    } catch (error: any) {
      toast.error(error?.response?.data || "Failed to remove member");
    } finally {
      setCollaboratorToDelete(null);
      setDeleteModalOpen(false);
    }
  };

  // Sort collaborators: owner first, then by status (active before pending)
  const sortedCollaborators = [...collaborators].sort((a, b) => {
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
      id="sharing"
      data-section-id="sharing"
      className={cn(className, "flex flex-col gap-4")}
    >
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Sharing</h2>
        
        {isOwner && (
          <button
            className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200"
            onClick={() => setIsInviteOpen(true)}
          >
            <Plus size={16} strokeWidth={3} />
            <span className="text-sm font-medium">Add member</span>
          </button>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {sortedCollaborators.map((collaborator) => (
          <CollaboratorCard
            key={collaborator.id}
            collaborator={collaborator}
            onDelete={isOwner ? handleDeleteClick : undefined}
          />
        ))}

        {sortedCollaborators.length === 0 && (
          <div className="p-6 bg-gray-50 rounded-lg text-center text-gray-400 text-sm">
            No members shared. {isOwner && "Click 'Add member' to start sharing."}
          </div>
        )}
      </div>

      {isOwner && (
        <InviteTeammateDialog
          open={isInviteOpen}
          onOpenChange={setIsInviteOpen}
          onInvite={handleInvite}
          existingTeammateIds={collaborators.map((c) => c.userId)}
        />
      )}

      <ConfirmDeleteModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title="Remove Member"
        description={`Are you sure you want to remove ${
          collaboratorToDelete?.name || collaboratorToDelete?.username
        } from this plan? They will lose access immediately.`}
        onConfirm={handleConfirmDelete}
      />
    </section>
  );
});

export default Sharing;
