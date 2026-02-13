import Link from "next/link";

type AdminLegalActionsProps = {
  docKey: "terms_of_service" | "privacy_policy";
};

export default function AdminLegalActions({ docKey }: AdminLegalActionsProps) {
  const editHref = docKey === "terms_of_service" ? "/admin/legal/terms" : "/admin/legal/privacy";
  return (
    <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      Admin tools (requires admin login):{" "}
      <Link href={editHref} className="font-semibold underline">
        Edit and publish this document
      </Link>
    </div>
  );
}
