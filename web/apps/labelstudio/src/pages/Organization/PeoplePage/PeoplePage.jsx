import { useCallback, useMemo, useState } from "react";
import { Block, Elem } from "../../../utils/bem";
import "./PeoplePage.scss";
import { PeopleListTable } from "./PeopleListTable";
import { SelectedUserPanel } from "./SelectedUserPanel";
import { useCurrentUserAtom } from "@humansignal/core/lib/hooks/useCurrentUser";

export const PeoplePage = () => {
  const { user } = useCurrentUserAtom();
  const isSuperuser = user?.is_superuser === true;

  const [selectedUser, setSelectedUser] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const selectUser = useCallback((user) => {
    setSelectedUser(user);
    localStorage.setItem("selectedPeopleUser", user?.id);
  }, []);

  const handleUserUpdate = useCallback((updatedUser) => {
    setSelectedUser(updatedUser);
    setRefreshKey((prev) => prev + 1);
  }, []);

  const defaultSelected = useMemo(() => {
    return localStorage.getItem("selectedPeopleUser");
  }, []);

  if (!isSuperuser) {
    return (
      <Block name="people">
        <Elem name="content">
          <div className="flex items-center justify-center h-full">
            <p className="text-neutral-content-subtle">Only superusers can access this page.</p>
          </div>
        </Elem>
      </Block>
    );
  }

  return (
    <Block name="people">
      <Elem name="content">
        <PeopleListTable
          selectedUser={selectedUser}
          defaultSelected={defaultSelected}
          onSelect={(user) => selectUser(user)}
          refreshKey={refreshKey}
        />

        {selectedUser && (
          <SelectedUserPanel user={selectedUser} onClose={() => selectUser(null)} onUserUpdate={handleUserUpdate} />
        )}
      </Elem>
    </Block>
  );
};

PeoplePage.title = "People";
PeoplePage.path = "/people";
