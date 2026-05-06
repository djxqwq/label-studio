import { format } from "date-fns";
import { IconCross, IconCheck } from "@humansignal/icons";
import { Userpic, Button, Select } from "@humansignal/ui";
import { Block, Elem } from "../../../utils/bem";
import { useAPI } from "../../../providers/ApiProvider";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useToast } from "@humansignal/ui";
import "./SelectedUser.scss";

export const SelectedUserPanel = ({ user, currentUser, canManageOrganizations = false, onClose, onUserUpdate }) => {
  const api = useAPI();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [selectedOrgToAdd, setSelectedOrgToAdd] = useState(null);
  const [selectedActiveOrg, setSelectedActiveOrg] = useState(user.active_organization);
  const canViewOrganizations = canManageOrganizations || currentUser?.id === user.id;
  const canUpdateActiveOrganization = canManageOrganizations || currentUser?.id === user.id;

  useEffect(() => {
    setSelectedActiveOrg(user.active_organization);
  }, [user.active_organization]);

  const fullName = [user.first_name, user.last_name]
    .filter((n) => !!n)
    .join(" ")
    .trim();

  const userOrgsQuery = useQuery({
    queryKey: ["userOrganizations", user.id],
    enabled: canViewOrganizations,
    async queryFn() {
      const response = await api.callApi("userOrganizations", {
        params: { pk: user.id },
      });
      return response || [];
    },
    staleTime: 30000,
    cacheTime: 60000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const allOrgsQuery = useQuery({
    queryKey: ["allOrganizations"],
    enabled: canManageOrganizations,
    async queryFn() {
      const response = await api.callApi("allOrganizations");
      return response || [];
    },
    staleTime: 60000,
    cacheTime: 120000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const addOrgMutation = useMutation({
    async mutationFn(orgId) {
      await api.callApi("addUserToOrganization", {
        params: { pk: user.id },
        body: { organization_id: orgId },
      });
    },
    onSuccess: () => {
      toast.show({ message: "User added to organization" });
      queryClient.invalidateQueries({ queryKey: ["userOrganizations", user.id] });
      setSelectedOrgToAdd(null);
    },
    onError: (error) => {
      toast.show({
        message: error?.message || "Failed to add user to organization",
        type: "error",
      });
    },
  });

  const removeOrgMutation = useMutation({
    async mutationFn(orgId) {
      await api.callApi("removeUserFromOrganization", {
        params: { pk: user.id, orgId },
      });
    },
    onSuccess: () => {
      toast.show({ message: "User removed from organization" });
      queryClient.invalidateQueries({ queryKey: ["userOrganizations", user.id] });
    },
    onError: (error) => {
      toast.show({
        message: error?.message || "Failed to remove user from organization",
        type: "error",
      });
    },
  });

  const updateActiveOrgMutation = useMutation({
    async mutationFn(orgId) {
      const response = await api.callApi("updateUserActiveOrganization", {
        params: { pk: user.id },
        body: { active_organization: orgId },
      });
      return response;
    },
    onSuccess: (response) => {
      toast.show({ message: "Active organization updated successfully" });
      setSelectedActiveOrg(response?.active_organization);
      queryClient.invalidateQueries({ queryKey: ["userOrganizations", user.id] });
      if (onUserUpdate) {
        onUserUpdate({
          ...user,
          active_organization: response?.active_organization,
          active_organization_meta: response?.active_organization_meta,
        });
      }
    },
    onError: (error) => {
      toast.show({
        message: error?.message || "Failed to update active organization",
        type: "error",
      });
    },
  });

  const handleSetActiveOrg = (orgId) => {
    if (orgId && orgId !== selectedActiveOrg) {
      updateActiveOrgMutation.mutate(orgId);
    }
  };

  const availableOrgsToAdd = allOrgsQuery.data?.filter(
    (org) => !userOrgsQuery.data?.some((userOrg) => userOrg.id === org.id),
  );

  const handleAddToOrg = () => {
    if (selectedOrgToAdd) {
      addOrgMutation.mutate(selectedOrgToAdd);
    }
  };

  const handleRemoveFromOrg = (orgId) => {
    removeOrgMutation.mutate(orgId);
  };

  return (
    <Block name="user-info">
      <Button
        look="string"
        onClick={onClose}
        className="absolute top-[20px] right-[24px]"
        aria-label="Close user details"
      >
        <IconCross />
      </Button>

      <Elem name="header">
        <Userpic user={user} style={{ width: 64, height: 64, fontSize: 28 }} />
        <Elem name="info-wrapper">
          {fullName && <Elem name="full-name">{fullName}</Elem>}
          <Elem tag="p" name="email">
            {user.email}
          </Elem>
        </Elem>
      </Elem>

      {user.phone && (
        <Elem name="section">
          <a href={`tel:${user.phone}`}>{user.phone}</a>
        </Elem>
      )}

      <Elem name="section">
        <Elem name="section-title">Active Team</Elem>
        {canUpdateActiveOrganization ? (
          <Elem name="active-org-selector">
            <Select
              value={selectedActiveOrg}
              options={
                userOrgsQuery.data?.map((org) => ({
                  label: org.title,
                  value: org.id,
                })) || []
              }
              onChange={(val) => handleSetActiveOrg(Number(val))}
              placeholder="Select active team"
              disabled={updateActiveOrgMutation.isPending || !userOrgsQuery.data?.length}
            />
            {updateActiveOrgMutation.isPending && <Elem name="loading-text">Updating...</Elem>}
          </Elem>
        ) : (
          <Elem name="loading-text">{user.active_organization_meta?.title || "N/A"}</Elem>
        )}
      </Elem>

      <Elem name="section">
        <Elem name="section-title">All Teams</Elem>

        {canViewOrganizations && userOrgsQuery.isLoading && <Elem name="loading-text">Loading...</Elem>}

        {canViewOrganizations && userOrgsQuery.data && userOrgsQuery.data.length > 0 && (
          <Elem name="orgs-list">
            {userOrgsQuery.data.map((org) => {
              const isActive = org.id === selectedActiveOrg;
              return (
                <Elem key={org.id} name="org-item" mod={{ active: isActive }}>
                  <Elem name="org-name">
                    {org.title}
                    {isActive && (
                      <Elem name="active-badge">
                        <IconCheck />
                        <span>Active</span>
                      </Elem>
                    )}
                  </Elem>
                  {canManageOrganizations && (
                    <Button
                      look="outlined"
                      size="small"
                      onClick={() => handleRemoveFromOrg(org.id)}
                      disabled={removeOrgMutation.isPending}
                    >
                      Remove
                    </Button>
                  )}
                </Elem>
              );
            })}
          </Elem>
        )}

        {canViewOrganizations && userOrgsQuery.data && userOrgsQuery.data.length === 0 && (
          <Elem name="empty-text">No organizations assigned</Elem>
        )}

        {canManageOrganizations && (
          <Elem name="add-org" className="mt-4">
            <Elem name="add-org-label">Add to organization:</Elem>
            <Elem name="add-org-controls">
              <Select
                value={selectedOrgToAdd}
                options={
                  availableOrgsToAdd?.map((org) => ({
                    label: org.title,
                    value: org.id,
                  })) || []
                }
                onChange={(val) => setSelectedOrgToAdd(Number(val))}
                placeholder="Select organization"
                disabled={addOrgMutation.isPending}
              />
              <Button onClick={handleAddToOrg} disabled={!selectedOrgToAdd || addOrgMutation.isPending}>
                {addOrgMutation.isPending ? "Adding..." : "Add"}
              </Button>
            </Elem>
          </Elem>
        )}
      </Elem>

      <Elem tag="p" name="last-active">
        Last activity on: {user.last_activity ? format(new Date(user.last_activity), "dd MMM yyyy, KK:mm a") : "N/A"}
      </Elem>
    </Block>
  );
};
