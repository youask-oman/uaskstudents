import { redirect } from "next/navigation";

export default function LegacySubscriptionsRedirect() {
  redirect("/admin/billing");
}

