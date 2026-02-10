import { redirect } from "next/navigation";

export default function LegacyPaymentsRedirect() {
    redirect("/adminpayments");
}
