import { OrganizationListPage } from "./OrganizationListPage/OrganizationListPage";

const SimpleLayout = ({ children }) => {
  return <div className="p-8">{children}</div>;
};

export const OrganizationPage = {
  title: "Organization",
  path: "/organization",
  exact: true,
  layout: SimpleLayout,
  component: OrganizationListPage,
};
