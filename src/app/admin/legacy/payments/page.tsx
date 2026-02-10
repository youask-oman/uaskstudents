import { redirect } from "next/navigation";

const PAGE_TITLE = "Legacy Payments";

export default function LegacyPaymentsRedirect() {
    redirect("/adminpayments");
}
