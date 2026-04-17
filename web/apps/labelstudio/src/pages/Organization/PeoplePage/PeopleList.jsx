import { formatDistance } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { Userpic } from "@humansignal/ui";
import { Pagination, Spinner } from "../../../components";
import { useAPI } from "../../../providers/ApiProvider";
import { Block, Elem } from "../../../utils/bem";
import "./PeopleList.scss";
import { CopyableTooltip } from "../../../components/CopyableTooltip/CopyableTooltip";

export const PeopleList = ({ onSelect, selectedUser, defaultSelected, organizationId }) => {
  const api = useAPI();
  const [usersList, setUsersList] = useState();
  const [currentPage, setCurrentPage] = useState(1);
  const [currentPageSize, setCurrentPageSize] = useState(30);
  const [totalItems, setTotalItems] = useState(0);

  const fetchUsers = useCallback(
    async (page, pageSize) => {
      if (!organizationId) return;

      try {
        const response = await api.callApi("memberships", {
          params: {
            pk: organizationId,
            contributed_to_projects: 1,
            page,
            page_size: pageSize,
          },
        });

        if (response) {
          setUsersList(response.results || []);
          setTotalItems(response.count || 0);
        }
      } catch (error) {
        console.error("Failed to fetch members:", error);
        setUsersList([]);
        setTotalItems(0);
      }
    },
    [organizationId],
  );

  const selectUser = useCallback(
    (user) => {
      if (selectedUser?.id === user.id) {
        onSelect?.(null);
      } else {
        onSelect?.(user);
      }
    },
    [selectedUser],
  );

  useEffect(() => {
    if (organizationId) {
      fetchUsers(currentPage, currentPageSize);
    }
  }, [organizationId, currentPage, currentPageSize, fetchUsers]);

  useEffect(() => {
    if (defaultSelected && usersList) {
      const selected = usersList.find(({ user }) => user.id === Number(defaultSelected));
      if (selected) selectUser(selected.user);
    }
  }, [usersList, defaultSelected]);

  const handlePageChange = (page, pageSize) => {
    setCurrentPage(page);
    setCurrentPageSize(pageSize);
    fetchUsers(page, pageSize);
  };

  if (!organizationId) {
    return <p className="text-neutral-content-subtle">Select an organization to view members</p>;
  }

  return (
    <Block name="people-list">
      <Elem name="wrapper">
        {usersList === undefined ? (
          <Elem name="loading">
            <Spinner size={36} />
          </Elem>
        ) : usersList.length === 0 ? (
          <Elem name="empty">
            <p className="text-neutral-content-subtle py-4">No members in this organization</p>
          </Elem>
        ) : (
          <Elem name="users">
            <Elem name="header">
              <Elem name="column" mix="avatar" />
              <Elem name="column" mix="email">
                Email
              </Elem>
              <Elem name="column" mix="name">
                Name
              </Elem>
              <Elem name="column" mix="last-activity">
                Last Activity
              </Elem>
            </Elem>
            <Elem name="body">
              {usersList.map(({ user }) => {
                const active = user.id === selectedUser?.id;

                return (
                  <Elem key={`user-${user.id}`} name="user" mod={{ active }} onClick={() => selectUser(user)}>
                    <Elem name="field" mix="avatar">
                      <CopyableTooltip title={`User ID: ${user.id}`} textForCopy={user.id}>
                        <Userpic user={user} style={{ width: 28, height: 28 }} />
                      </CopyableTooltip>
                    </Elem>
                    <Elem name="field" mix="email">
                      {user.email}
                    </Elem>
                    <Elem name="field" mix="name">
                      {user.first_name} {user.last_name}
                    </Elem>
                    <Elem name="field" mix="last-activity">
                      {formatDistance(new Date(user.last_activity), new Date(), { addSuffix: true })}
                    </Elem>
                  </Elem>
                );
              })}
            </Elem>
          </Elem>
        )}
      </Elem>
      {totalItems > 0 && (
        <Pagination
          page={currentPage}
          totalItems={totalItems}
          pageSize={currentPageSize}
          pageSizeOptions={[30, 50, 100]}
          onPageLoad={handlePageChange}
          style={{ paddingTop: 16 }}
        />
      )}
    </Block>
  );
};
