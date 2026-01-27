"use client";

import {
  getMyPlans,
  getSharedPlans,
  getPendingInvitations,
  deletePlan,
} from "@/api/plan/plan";
import {
  respondToInvitation,
  deleteParticipant,
} from "@/api/participant/participant";
import { useAppContext } from "@/contexts/AppContext";
import { InvitationStatus } from "@/api/participant/types";
import { Plan } from "@/types/plan";
import { AxiosError } from "axios";
import { useEffect, useState, useCallback } from "react";
import toast from "react-hot-toast";
import PlanSection from "./components/plan-section";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { PaginatedResult } from "@/types/paginated";
import { Clock, User, Users } from "lucide-react";

const PAGE_SIZE = 8;

export default function MyPlansPage() {
  const { user } = useAppContext();
  // State for each section
  const [pendingData, setPendingData] = useState<PaginatedResult<Plan> | null>(
    null,
  );
  const [myPlansData, setMyPlansData] = useState<PaginatedResult<Plan> | null>(
    null,
  );
  const [sharedData, setSharedData] = useState<PaginatedResult<Plan> | null>(
    null,
  );

  // Loading states
  const [pendingLoading, setPendingLoading] = useState(true);
  const [myPlansLoading, setMyPlansLoading] = useState(true);
  const [sharedLoading, setSharedLoading] = useState(true);

  // Pages
  const [pendingPage, setPendingPage] = useState(1);
  const [myPlansPage, setMyPlansPage] = useState(1);
  const [sharedPage, setSharedPage] = useState(1);

  // Delete confirmation
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [planToDelete, setPlanToDelete] = useState<Plan | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Leave confirmation
  const [leaveModalOpen, setLeaveModalOpen] = useState(false);
  const [planToLeave, setPlanToLeave] = useState<Plan | null>(null);
  const [isLeaving, setIsLeaving] = useState(false);

  const fetchPendingInvitations = useCallback(async (page: number) => {
    setPendingLoading(true);
    try {
      const response = await getPendingInvitations(page, PAGE_SIZE);
      setPendingData(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to load invitations");
      }
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const fetchMyPlans = useCallback(async (page: number) => {
    setMyPlansLoading(true);
    try {
      const response = await getMyPlans(page, PAGE_SIZE);
      setMyPlansData(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to load your plans");
      }
    } finally {
      setMyPlansLoading(false);
    }
  }, []);

  const fetchSharedPlans = useCallback(async (page: number) => {
    setSharedLoading(true);
    try {
      const response = await getSharedPlans(page, PAGE_SIZE);
      setSharedData(response);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to load shared plans");
      }
    } finally {
      setSharedLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPendingInvitations(pendingPage);
  }, [pendingPage, fetchPendingInvitations]);

  useEffect(() => {
    fetchMyPlans(myPlansPage);
  }, [myPlansPage, fetchMyPlans]);

  useEffect(() => {
    fetchSharedPlans(sharedPage);
  }, [sharedPage, fetchSharedPlans]);

  const handleAccept = async (plan: Plan) => {
    let participantId = plan.participantId;

    // Fallback: Try to find participantId from participants list if current user is known
    if (!participantId && user) {
      const myParticipant = plan.participants?.find(
        (p) => p.userId === user.id,
      );
      if (myParticipant) {
        participantId = myParticipant.id;
      }
    }

    if (!participantId) {
      console.error("Missing participantId for plan:", plan, "User:", user);
      toast.error("Cannot identify your participant ID for this plan.");
      return;
    }

    try {
      await respondToInvitation(participantId, InvitationStatus.Accepted);
      toast.success("Invitation accepted!");
      // Refresh both pending and shared sections
      fetchPendingInvitations(pendingPage);
      fetchSharedPlans(sharedPage);
    } catch (error) {
      console.error("Error accepting invitation:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to accept invitation");
      }
    }
  };

  const handleDecline = async (plan: Plan) => {
    let participantId = plan.participantId;

    // Fallback: Try to find participantId from participants list if current user is known
    if (!participantId && user) {
      const myParticipant = plan.participants?.find(
        (p) => p.userId === user.id,
      );
      if (myParticipant) {
        participantId = myParticipant.id;
      }
    }

    if (!participantId) {
      console.error("Missing participantId for plan:", plan, "User:", user);
      toast.error("Cannot identify your participant ID for this plan.");
      return;
    }

    try {
      await respondToInvitation(participantId, InvitationStatus.Declined);
      toast.success("Invitation declined");
      fetchPendingInvitations(pendingPage);
    } catch (error) {
      console.error("Error declining invitation:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to decline invitation");
      }
    }
  };

  const handleDeleteClick = (plan: Plan) => {
    setPlanToDelete(plan);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!planToDelete) return;
    setIsDeleting(true);
    try {
      await deletePlan(planToDelete.id);
      toast.success("Plan deleted successfully");
      setDeleteModalOpen(false);
      setPlanToDelete(null);
      fetchMyPlans(myPlansPage);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to delete plan");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleLeaveClick = (plan: Plan) => {
    setPlanToLeave(plan);
    setLeaveModalOpen(true);
  };

  const handleConfirmLeave = async () => {
    if (!planToLeave) return;

    let participantId = planToLeave.participantId;

    if (!participantId && user) {
      const myParticipant = planToLeave.participants?.find(
        (p) => p.userId === user.id,
      );
      if (myParticipant) {
        participantId = myParticipant.id;
      }
    }

    if (!participantId) {
      toast.error("Could not determine your participant ID for this plan.");
      return;
    }

    setIsLeaving(true);
    try {
      await deleteParticipant(participantId);
      toast.success("Left plan successfully");
      setLeaveModalOpen(false);
      setPlanToLeave(null);
      fetchSharedPlans(sharedPage);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to leave plan");
      }
    } finally {
      setIsLeaving(false);
    }
  };

  return (
    <div className="w-full h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-8">
        {/* Pending Invitations Section */}
        <PlanSection
          title="Pending Invitations"
          icon={
            <img
              src="/images/plans/invite.png"
              alt=""
              className="w-6 h-6 text-blue-600"
            />
          }
          data={pendingData}
          isLoading={pendingLoading}
          variant="pending"
          emptyMessage="No pending invitations"
          onPageChange={setPendingPage}
          onAccept={handleAccept}
          onDecline={handleDecline}
        />

        {/* Your Plans Section */}
        <PlanSection
          title="Your Plans"
          icon={
            <img
              src="/images/plans/plan.png"
              alt=""
              className="w-6 h-6 text-blue-600"
            />
          }
          data={myPlansData}
          isLoading={myPlansLoading}
          variant="owned"
          emptyMessage="You haven't created any plans yet"
          onPageChange={setMyPlansPage}
          onDelete={handleDeleteClick}
        />

        {/* Shared With Me Section */}
        <PlanSection
          title="Shared With Me"
          icon={
            <img
              src="/images/plans/shared.png"
              alt=""
              className="w-6 h-6 text-blue-600"
            />
          }
          data={sharedData}
          isLoading={sharedLoading}
          variant="shared"
          emptyMessage="No shared plans"
          onPageChange={setSharedPage}
          onLeave={handleLeaveClick}
        />

        {/* Delete Confirmation Modal */}
        <ConfirmDeleteModal
          open={deleteModalOpen}
          onOpenChange={(open: boolean) => {
            setDeleteModalOpen(open);
            if (!open) setPlanToDelete(null);
          }}
          onConfirm={handleConfirmDelete}
          title="Delete Plan"
          description={`Are you sure you want to delete "${planToDelete?.name}"? This action cannot be undone and all plan data will be permanently removed.`}
        />

        {/* Leave Confirmation Modal */}
        <ConfirmDeleteModal
          open={leaveModalOpen}
          onOpenChange={(open: boolean) => {
            setLeaveModalOpen(open);
            if (!open) setPlanToLeave(null);
          }}
          onConfirm={handleConfirmLeave}
          title="Leave Plan"
          description={`Are you sure you want to leave "${planToLeave?.name}"? You will lose access to this plan.`}
        />
      </div>
    </div>
  );
}
