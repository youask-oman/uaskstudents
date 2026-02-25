"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import navManifest from "../../../admin_nav_manifest.json";

type NavItem = {
  type?: string;
  label?: string;
  href?: string;
  page_title?: string;
};

type IntroMeta = {
  title: string;
  description: string;
  actions: string[];
  dataImpact?: string;
};

const explicitMeta: Record<string, IntroMeta> = {
  "/admin/dashboard": {
    title: "Analytics Dashboard",
    description: "Central view of platform health, demand, cost, and quality trends.",
    actions: [
      "Review request, cost, and latency trends.",
      "Inspect model routing behavior and anomalies.",
      "Navigate to specialized admin tools quickly.",
    ],
    dataImpact: "Read-only analytics. Does not modify production data.",
  },
  "/admin/whatsapp-monitor": {
    title: "WhatsApp Monitor",
    description: "Operational message stream and queue monitor for WhatsApp integration.",
    actions: [
      "Track inbound/outbound events in near real-time.",
      "Inspect message details and queue depth.",
      "Clear monitor stream artifacts when needed.",
    ],
    dataImpact: "Monitor clear action is destructive for event history cache only.",
  },
  "/admin/whatsapp-abuse": {
    title: "WhatsApp Abuse Operations",
    description: "Anti-abuse operations console for lock, circuit, offender, and audit workflows.",
    actions: [
      "Apply or clear temporary locks for users/phones.",
      "Toggle solve/media circuit breakers during incidents.",
      "Review top offenders, drop reasons, and audit events.",
      "Export abuse telemetry and action logs to CSV.",
    ],
    dataImpact: "Writes control state to Redis and can temporarily block user traffic.",
  },
};

function prettifyPathname(pathname: string): string {
  const clean = pathname
    .replace(/^\/admin\/?/, "")
    .replace(/\[[^\]]+\]/g, "detail")
    .replace(/[-_]/g, " ")
    .replace(/\//g, " / ")
    .trim();
  if (!clean) return "Admin Console";
  return clean
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function defaultActions(pathname: string): string[] {
  const p = pathname.toLowerCase();
  if (p.includes("billing")) {
    return [
      "Review billing and credit records.",
      "Adjust billing configuration and operational settings.",
      "Export financial data for reconciliation.",
    ];
  }
  if (p.includes("prompt") || p.includes("schema")) {
    return [
      "Review active prompt/schema configuration.",
      "Publish updates and rollback when required.",
      "Validate consistency across runtime bindings.",
    ];
  }
  if (p.includes("user")) {
    return [
      "Inspect account metadata and status.",
      "Apply administrative updates safely.",
      "Audit user-specific usage and activity signals.",
    ];
  }
  return [
    "Review current operational state for this area.",
    "Apply administrative controls available on this page.",
    "Export or verify records for audit and support workflows.",
  ];
}

function deriveMeta(pathname: string): IntroMeta {
  const explicit = explicitMeta[pathname];
  if (explicit) return explicit;

  const navItems: NavItem[] = Array.isArray((navManifest as { nav_items?: NavItem[] }).nav_items)
    ? ((navManifest as { nav_items?: NavItem[] }).nav_items as NavItem[])
    : [];
  const navItem = navItems.find((n) => n.type === "link" && n.href === pathname);

  const title = navItem?.page_title || navItem?.label || prettifyPathname(pathname);
  const description =
    `Administrative workspace for ${title}. This page provides operational controls and oversight for this domain.`;

  return {
    title,
    description,
    actions: defaultActions(pathname),
    dataImpact: "Some actions may write production settings or metadata. Review controls before applying changes.",
  };
}

export default function AdminPageIntro() {
  const pathname = usePathname();
  const isAdminPath = pathname?.startsWith("/admin");

  const meta = useMemo(() => (isAdminPath ? deriveMeta(pathname) : null), [isAdminPath, pathname]);
  if (!isAdminPath || !meta) return null;

  return (
    <section data-testid="admin-page-intro" className="px-8 pt-6 pb-4 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/30">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{meta.title}</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{meta.description}</p>
      <div className="mt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">What You Can Do Here</p>
        <ul className="mt-1 list-disc pl-5 text-sm text-slate-700 dark:text-slate-200">
          {meta.actions.slice(0, 6).map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </div>
      {meta.dataImpact && (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
          Data impact: {meta.dataImpact}
        </p>
      )}
    </section>
  );
}
