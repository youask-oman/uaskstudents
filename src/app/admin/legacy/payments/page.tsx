import { redirect } from "next/navigation";

const PAGE_TITLE = "Legacy Payments";
void PAGE_TITLE;

export default function LegacyPaymentsRedirect() {
    redirect("/adminpayments");
}
