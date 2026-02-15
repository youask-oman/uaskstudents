import { redirect } from "next/navigation";

export default function AdminPaymentsSubscriptionsRedirect() {
  redirect("/adminpayments/topups");
}

