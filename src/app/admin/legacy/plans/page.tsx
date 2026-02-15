import { redirect } from "next/navigation";

const PAGE_TITLE = "Legacy Plans";
void PAGE_TITLE;

export default function LegacyPlansAliasPage() {
  redirect("/admin/billing");
}
