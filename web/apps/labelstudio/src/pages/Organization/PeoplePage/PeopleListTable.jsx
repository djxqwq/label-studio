import { formatDistance } from "date-fns";
import { useCallback, useEffect, useState, useRef } from "react";
import { Userpic } from "@humansignal/ui";
import { Pagination, Spinner } from "../../../components";
import { usePage, usePageSize } from "../../../components/Pagination/Pagination";
import { useAPI } from "../../../providers/ApiProvider";
import { Block, Elem } from "../../../utils/bem";
import "./PeopleList.scss";
import { CopyableTooltip } from "../../../components/CopyableTooltip/CopyableTooltip";
import { Input } from "../../../components/Form";

export const PeopleListTable = ({ onSelect, selectedUser, defaultSelected, refreshKey }) => {
  const api = useAPI();
  const [usersList, setUsersList] = useState();
  const [currentPage] = usePage("page", 1);
  const [currentPageSize] = usePageSize("page_size", 30);
  const [totalItems, setTotalItems] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const searchTimeoutRef = useRef(null);

  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery]);

  const fetchUsers = useCallback(
    async (page, pageSize) => {
      const response = await api.callApi("users", {
        params: {
          page,
          page_size: pageSize,
          search: debouncedSearch || undefined,
        },
      });

      if (response?.results) {
        setUsersList(response.results);
        setTotalItems(response.count);
      } else if (Array.isArray(response)) {
        setUsersList(response);
        setTotalItems(response.length);
      }
    },
    [api, debouncedSearch],
  );

  const handleSelectUser = useCallback(
    (user) => {
      if (selectedUser?.id === user.id) {
        onSelect?.(null);
      } else {
        onSelect?.(user);
      }
    },
    [selectedUser?.id, onSelect],
  );

  useEffect(() => {
    fetchUsers(currentPage, currentPageSize);
  }, [fetchUsers, currentPage, currentPageSize, refreshKey]);

  const initialSelectionDone = useRef(false);

  useEffect(() => {
    if (defaultSelected && usersList && !initialSelectionDone.current) {
      const selected = usersList.find((user) => user.id === Number(defaultSelected));
      if (selected) {
        handleSelectUser(selected);
        initialSelectionDone.current = true;
      }
    }
  }, [usersList, defaultSelected]);

  return (
    <Block name="people-list">
      <Elem name="search" className="mb-4">
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by email or name..."
          style={{ width: "100%" }}
        />
      </Elem>

      <Elem name="wrapper">
        {usersList ? (
          usersList.length > 0 ? (
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
                {usersList.map((user) => {
                  const active = user.id === selectedUser?.id;

                  return (
                    <Elem key={`user-${user.id}`} name="user" mod={{ active }} onClick={() => handleSelectUser(user)}>
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
                        {user.last_activity
                          ? formatDistance(new Date(user.last_activity), new Date(), { addSuffix: true })
                          : "N/A"}
                      </Elem>
                    </Elem>
                  );
                })}
              </Elem>
            </Elem>
          ) : (
            <Elem name="loading">
              <p className="text-neutral-content-subtle">No users found</p>
            </Elem>
          )
        ) : (
          <Elem name="loading">
            <Spinner size={36} />
          </Elem>
        )}
      </Elem>
      <Pagination
        page={currentPage}
        urlParamName="page"
        totalItems={totalItems}
        pageSize={currentPageSize}
        pageSizeOptions={[30, 50, 100]}
        onPageLoad={fetchUsers}
        style={{ paddingTop: 16 }}
      />
    </Block>
  );
};
