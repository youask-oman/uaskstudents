import { redirect } from "next/navigation";

const PAGE_TITLE = "Legacy Plans";

export default function LegacyPlansRedirect() {
    redirect("/admin/legacy/plans");
}
