import { Button, Typography } from "@humansignal/ui";
import { Space } from "@humansignal/ui/lib/space/space";
import { Block } from "apps/labelstudio/src/components/Menu/MenuContext";
import { API } from "apps/labelstudio/src/providers/ApiProvider";
import { useCurrentUserAtom } from "@humansignal/core/lib/hooks/useCurrentUser";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { CreateOrganizationModal } from "../PeoplePage/CreateOrganizationModal";
import { PeopleList } from "../PeoplePage/PeopleList";
import { useToast } from "@humansignal/ui";

interface Organization {
  id: number;
  title: string;
  contact_info: string | null;
  created_at: string;
  member_count: number;
}

export const OrganizationListPage = () => {
  const { user, loaded } = useCurrentUserAtom();
  const isSuperuser = user?.is_superuser === true;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [selectedOrgId, setSelectedOrgId] = useState<number | null>(null);

  const organizationsQuery = useQuery({
    queryKey: ["organizations", isSuperuser],
    async queryFn() {
      if (isSuperuser) {
        return await API.invoke<Organization[]>("allOrganizations");
      }
      return await API.invoke<Organization[]>("organizations");
    },
    enabled: loaded,
  });

  const deleteMutation = useMutation({
    async mutationFn(orgId: number) {
      await API.invoke("deleteOrganization", { pk: orgId });
    },
    onSuccess: () => {
      toast.show({ message: "Organization deleted successfully" });
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      if (selectedOrgId) {
        setSelectedOrgId(null);
      }
    },
    onError: (error) => {
      toast.show({
        message: error?.message || "Failed to delete organization",
        type: "error",
      });
    },
  });

  const handleOrgClick = (orgId: number) => {
    setSelectedOrgId(orgId === selectedOrgId ? null : orgId);
  };

  const handleDeleteOrg = (orgId: number, orgTitle: string) => {
    if (confirm(`Are you sure you want to delete organization "${orgTitle}"? This action cannot be undone.`)) {
      deleteMutation.mutate(orgId);
    }
  };

  const selectedOrg = organizationsQuery.data?.find((org) => org.id === selectedOrgId);

  return (
    <Block name="organization-list">
      <div className="flex gap-4 max-w-[1200px] mx-auto">
        <div className="w-1/2">
          <div className="py-4">
            <Space spread>
              <Typography size="large" weight="bold">
                {isSuperuser ? "All Organizations" : "My Organizations"}
              </Typography>
              {isSuperuser && (
                <Button
                  look="outlined"
                  onClick={() => setCreateOrgOpen(true)}
                  aria-label="Create new organization"
                >
                  Create Organization
                </Button>
              )}
            </Space>
          </div>

          {organizationsQuery.isLoading && (
            <Typography size="medium">Loading...</Typography>
          )}

          {organizationsQuery.error && (
            <Typography size="medium" className="text-danger-default">
              Failed to load organizations
            </Typography>
          )}

          {organizationsQuery.data && organizationsQuery.data.length === 0 && (
            <Typography size="medium" className="text-neutral-content-subtle">
              No organizations found
            </Typography>
          )}

          {organizationsQuery.data && organizationsQuery.data.length > 0 && (
            <div className="space-y-2">
              {organizationsQuery.data.map((org: Organization) => (
                <div
                  key={org.id}
                  className={`p-3 border rounded-lg ${
                    selectedOrgId === org.id
                      ? "bg-primary-background-subtle border-primary-default"
                      : "hover:bg-neutral-background-subtle"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div
                      className="cursor-pointer flex-grow"
                      onClick={() => handleOrgClick(org.id)}
                    >
                      <Typography size="medium" weight="semibold">
                        {org.title}
                      </Typography>
                      <Typography size="small" className="text-neutral-content-subtle mt-1">
                        ID: {org.id} | Members: {org.member_count} | Created: {new Date(org.created_at).toLocaleDateString()}
                      </Typography>
                      {org.contact_info && (
                        <Typography size="small" className="text-neutral-content-subtle mt-1">
                          Contact: {org.contact_info}
                        </Typography>
                      )}
                    </div>
                    {isSuperuser && org.member_count === 0 && (
                      <Button
                        look="outlined"
                        size="small"
                        onClick={() => handleDeleteOrg(org.id, org.title)}
                        disabled={deleteMutation.isPending}
                        aria-label={`Delete organization ${org.title}`}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="w-1/2">
          {selectedOrg ? (
            <div>
              <div className="py-4">
                <Typography size="large" weight="bold">
                  Members of {selectedOrg.title}
                </Typography>
              </div>
              <PeopleList organizationId={selectedOrg.id} />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <Typography size="medium" className="text-neutral-content-subtle">
                Select an organization to view members
              </Typography>
            </div>
          )}
        </div>
      </div>

      <CreateOrganizationModal
        opened={createOrgOpen}
        onClosed={() => setCreateOrgOpen(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["organizations"] });
        }}
      />
    </Block>
  );
};

OrganizationListPage.title = "Organizations";