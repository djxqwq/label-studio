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

  const selectUser = useCallback(
    (selected) => {
      setSelectedUser(selected);

      if (!isSuperuser) return;

      if (selected?.id) {
        localStorage.setItem("selectedPeopleUser", selected.id);
      } else {
        localStorage.removeItem("selectedPeopleUser");
      }
    },
    [isSuperuser],
  );

  const handleUserUpdate = useCallback((updatedUser) => {
    setSelectedUser(updatedUser);
    setRefreshKey((prev) => prev + 1);
  }, []);

  const defaultSelected = useMemo(() => {
    if (isSuperuser) {
      return localStorage.getItem("selectedPeopleUser");
    }

    return user?.id ? String(user.id) : null;
  }, [isSuperuser, user?.id]);

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
          <SelectedUserPanel
            user={selectedUser}
            currentUser={user}
            canManageOrganizations={isSuperuser}
            onClose={() => selectUser(null)}
            onUserUpdate={handleUserUpdate}
          />
        )}
      </Elem>
    </Block>
  );
};

PeoplePage.title = "People";
PeoplePage.path = "/people";
