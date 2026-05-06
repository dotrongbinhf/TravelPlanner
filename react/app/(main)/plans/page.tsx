"use client";

import {
  getMyPlans,
  getSharedPlans,
  getPendingInvitations,
  deletePlan,
  clonePlan,
  PlanQueryParams,
} from "@/api/plan/plan";
import {
  respondToInvitation,
  deleteCollaborator,
} from "@/api/collaborator/collaborator";
import { useAppContext } from "@/contexts/AppContext";
import { InvitationStatus } from "@/api/collaborator/types";
import { Plan } from "@/types/plan";
import { AxiosError } from "axios";
import { useEffect, useState, useCallback, useRef } from "react";
import toast from "react-hot-toast";
import PlanSection from "./components/plan-section";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { PaginatedResult } from "@/types/paginated";
import {
  ToolbarState,
  DEFAULT_TOOLBAR_STATE,
} from "./components/plans-toolbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CustomDialog } from "@/components/custom-dialog";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

const PAGE_SIZE = 8;

// Convert toolbar state to API query params
function toolbarToParams(
  toolbar: ToolbarState,
  page: number,
): PlanQueryParams {
  const params: PlanQueryParams = {
    page,
    pageSize: PAGE_SIZE,
    sortBy: toolbar.sortField,
    sortOrder: toolbar.sortOrder,
  };
  if (toolbar.search.trim()) params.search = toolbar.search.trim();
  if (toolbar.dateFrom) params.dateFrom = toolbar.dateFrom.toISOString();
  if (toolbar.dateTo) params.dateTo = toolbar.dateTo.toISOString();
  if (toolbar.status !== "all") params.status = toolbar.status;
  return params;
}

export default function MyPlansPage() {
  const { user } = useAppContext();

  // ── Per-section toolbar state ─────────────────────────────────
  const [pendingToolbar, setPendingToolbar] = useState<ToolbarState>(
    DEFAULT_TOOLBAR_STATE,
  );
  const [myPlansToolbar, setMyPlansToolbar] = useState<ToolbarState>(
    DEFAULT_TOOLBAR_STATE,
  );
  const [sharedToolbar, setSharedToolbar] = useState<ToolbarState>(
    DEFAULT_TOOLBAR_STATE,
  );

  // ── Data state ────────────────────────────────────────────────
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

  // Clone
  const [cloneModalOpen, setCloneModalOpen] = useState(false);
  const [planToClone, setPlanToClone] = useState<Plan | null>(null);
  const [cloneName, setCloneName] = useState("");
  const [isCloning, setIsCloning] = useState(false);

  // ── Fetch functions ───────────────────────────────────────────
  const fetchPendingInvitations = useCallback(
    async (page: number) => {
      setPendingLoading(true);
      try {
        const response = await getPendingInvitations(
          toolbarToParams(pendingToolbar, page),
        );
        setPendingData(response);
      } catch (error) {
        if (error instanceof AxiosError) {
          toast.error(error.response?.data ?? "Failed to load invitations");
        }
      } finally {
        setPendingLoading(false);
      }
    },
    [pendingToolbar],
  );

  const fetchMyPlans = useCallback(
    async (page: number) => {
      setMyPlansLoading(true);
      try {
        const response = await getMyPlans(
          toolbarToParams(myPlansToolbar, page),
        );
        setMyPlansData(response);
      } catch (error) {
        if (error instanceof AxiosError) {
          toast.error(error.response?.data ?? "Failed to load your plans");
        }
      } finally {
        setMyPlansLoading(false);
      }
    },
    [myPlansToolbar],
  );

  const fetchSharedPlans = useCallback(
    async (page: number) => {
      setSharedLoading(true);
      try {
        const response = await getSharedPlans(
          toolbarToParams(sharedToolbar, page),
        );
        setSharedData(response);
      } catch (error) {
        if (error instanceof AxiosError) {
          toast.error(error.response?.data ?? "Failed to load shared plans");
        }
      } finally {
        setSharedLoading(false);
      }
    },
    [sharedToolbar],
  );

  // ── Effects: fetch on page or toolbar change ──────────────────
  useEffect(() => {
    fetchPendingInvitations(pendingPage);
  }, [pendingPage, fetchPendingInvitations]);

  useEffect(() => {
    fetchMyPlans(myPlansPage);
  }, [myPlansPage, fetchMyPlans]);

  useEffect(() => {
    fetchSharedPlans(sharedPage);
  }, [sharedPage, fetchSharedPlans]);

  // Reset page to 1 when toolbar changes
  const pendingToolbarRef = useRef(pendingToolbar);
  useEffect(() => {
    if (pendingToolbarRef.current !== pendingToolbar) {
      pendingToolbarRef.current = pendingToolbar;
      setPendingPage(1);
    }
  }, [pendingToolbar]);

  const myPlansToolbarRef = useRef(myPlansToolbar);
  useEffect(() => {
    if (myPlansToolbarRef.current !== myPlansToolbar) {
      myPlansToolbarRef.current = myPlansToolbar;
      setMyPlansPage(1);
    }
  }, [myPlansToolbar]);

  const sharedToolbarRef = useRef(sharedToolbar);
  useEffect(() => {
    if (sharedToolbarRef.current !== sharedToolbar) {
      sharedToolbarRef.current = sharedToolbar;
      setSharedPage(1);
    }
  }, [sharedToolbar]);

  // ── Helper: resolve collaborator ID ───────────────────────────
  const resolveCollaboratorId = (plan: Plan): string | undefined => {
    let collaboratorId = plan.collaboratorId;
    if (!collaboratorId && user) {
      const myCollaborator = plan.collaborators?.find(
        (c) => c.userId === user.id,
      );
      if (myCollaborator) {
        collaboratorId = myCollaborator.id;
      }
    }
    return collaboratorId;
  };

  // ── Handlers ──────────────────────────────────────────────────
  const handleAccept = async (plan: Plan) => {
    const collaboratorId = resolveCollaboratorId(plan);
    if (!collaboratorId) {
      toast.error("Cannot identify your collaborator ID for this plan.");
      return;
    }

    try {
      await respondToInvitation(collaboratorId, InvitationStatus.Accepted);
      toast.success("Invitation accepted!");
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
    const collaboratorId = resolveCollaboratorId(plan);
    if (!collaboratorId) {
      toast.error("Cannot identify your collaborator ID for this plan.");
      return;
    }

    try {
      await respondToInvitation(collaboratorId, InvitationStatus.Declined);
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

    const collaboratorId = resolveCollaboratorId(planToLeave);
    if (!collaboratorId) {
      toast.error("Could not determine your collaborator ID for this plan.");
      return;
    }

    setIsLeaving(true);
    try {
      await deleteCollaborator(collaboratorId);
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

  const handleCloneClick = (plan: Plan) => {
    setPlanToClone(plan);
    setCloneName(`Copy of "${plan.name}"`);
    setCloneModalOpen(true);
  };

  const handleConfirmClone = async () => {
    if (!planToClone) return;
    if (!cloneName.trim()) {
      toast.error("Plan name cannot be empty");
      return;
    }

    setIsCloning(true);
    try {
      await clonePlan(planToClone.id, cloneName.trim());
      toast.success("Plan cloned successfully!");
      setCloneModalOpen(false);
      setPlanToClone(null);
      setCloneName("");
      fetchMyPlans(myPlansPage);
    } catch (error) {
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Failed to clone plan");
      }
    } finally {
      setIsCloning(false);
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
          toolbarState={pendingToolbar}
          onToolbarChange={setPendingToolbar}
          currentPage={pendingPage}
          pageSize={PAGE_SIZE}
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
          onClone={handleCloneClick}
          toolbarState={myPlansToolbar}
          onToolbarChange={setMyPlansToolbar}
          currentPage={myPlansPage}
          pageSize={PAGE_SIZE}
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
          onClone={handleCloneClick}
          toolbarState={sharedToolbar}
          onToolbarChange={setSharedToolbar}
          currentPage={sharedPage}
          pageSize={PAGE_SIZE}
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

        {/* Clone Plan Dialog */}
        <CustomDialog
          open={cloneModalOpen}
          onOpenChange={(open) => {
            setCloneModalOpen(open);
            if (!open) {
              setPlanToClone(null);
              setCloneName("");
            }
          }}
          title="Clone Plan"
          description={`Create a copy of "${planToClone?.name}". The new plan will include itinerary, budget, packing lists, and notes, but not conversations or shared members.`}
          confirmLabel={
            isCloning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Cloning...
              </>
            ) : (
              "Clone Plan"
            )
          }
          isDisabled={isCloning || !cloneName.trim()}
          onCancel={() => {
            setCloneModalOpen(false);
            setPlanToClone(null);
            setCloneName("");
          }}
          onConfirm={handleConfirmClone}
          confirmClassName="bg-blue-600 hover:bg-blue-700"
        >
          <div className="flex flex-col gap-2 py-2">
            <Label htmlFor="clone-name">Plan Name</Label>
            <Input
              id="clone-name"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isCloning && cloneName.trim()) {
                  handleConfirmClone();
                }
              }}
              placeholder="Enter a name for the cloned plan"
            />
          </div>
        </CustomDialog>
      </div>
    </div>
  );
}
