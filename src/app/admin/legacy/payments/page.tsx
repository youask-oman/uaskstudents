import { redirect } from "next/navigation";

export const PAGE_TITLE = "Legacy Payments";

export default function LegacyPaymentsRedirect() {
    redirect("/adminpayments");
}
