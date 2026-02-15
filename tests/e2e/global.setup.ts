import { request, type FullConfig } from "@playwright/test";

type LoginResponse = {
  access_token: string;
  user_id: number;
  full_name: string;
  role: string;
};

type AdminUserListResponse = {
  users: Array<{ id: number; email: string; full_name: string; role: string }>;
};

const BACKEND_BASE = process.env.E2E_BACKEND_URL || "http://127.0.0.1:9000";
const DEFAULT_PASSWORD = process.env.E2E_DEFAULT_PASSWORD || "admin1234";

const seedUsers = [
  { key: "superadmin", email: process.env.E2E_SUPERADMIN_EMAIL || "admin@uask.ai", name: "E2E Super Admin", role: "superadmin", credits: 500 },
  { key: "admin", email: process.env.E2E_ADMIN_EMAIL || "e2e.admin@uask.ai", name: "E2E Admin", role: "admin", credits: 500 },
  { key: "support", email: process.env.E2E_SUPPORT_EMAIL || "e2e.support@uask.ai", name: "E2E Support", role: "support", credits: 500 },
  { key: "finance", email: process.env.E2E_FINANCE_EMAIL || "e2e.finance@uask.ai", name: "E2E Finance", role: "finance", credits: 500 },
  { key: "devops", email: process.env.E2E_DEVOPS_EMAIL || "e2e.devops@uask.ai", name: "E2E DevOps", role: "devops", credits: 500 },
  { key: "normal", email: process.env.E2E_NORMAL_EMAIL || "e2e.user@uask.ai", name: "E2E User", role: "student", credits: 500 },
  { key: "insufficient", email: process.env.E2E_INSUFFICIENT_EMAIL || "e2e.lowcredits@uask.ai", name: "E2E Low Credits", role: "student", credits: 2 },
] as const;

async function loginAs(api: Awaited<ReturnType<typeof request.newContext>>, email: string, password: string): Promise<LoginResponse> {
  const res = await api.post(`${BACKEND_BASE}/api/v1/login`, {
    data: { email, password },
  });
  if (!res.ok()) {
    throw new Error(`Login failed for ${email}: ${res.status()} ${await res.text()}`);
  }
  return (await res.json()) as LoginResponse;
}

async function ensureUser(
  api: Awaited<ReturnType<typeof request.newContext>>,
  superToken: string,
  email: string,
  fullName: string,
  role: string,
) {
  const headers = { Authorization: `Bearer ${superToken}` };
  const usersRes = await api.get(`${BACKEND_BASE}/api/v1/admin/users?offset=0&limit=500`, { headers });
  if (!usersRes.ok()) {
    throw new Error(`Failed to list users: ${usersRes.status()} ${await usersRes.text()}`);
  }
  const users = (await usersRes.json()) as AdminUserListResponse;
  let user = users.users.find((u) => u.email.toLowerCase() === email.toLowerCase());

  if (!user) {
    const inviteRes = await api.post(`${BACKEND_BASE}/api/v1/admin/invite`, {
      headers: { ...headers, "Content-Type": "application/json" },
      data: {
        full_name: fullName,
        email,
        password: DEFAULT_PASSWORD,
        academic_level: "University",
      },
    });
    if (!inviteRes.ok()) {
      throw new Error(`Failed to create user ${email}: ${inviteRes.status()} ${await inviteRes.text()}`);
    }
    const refreshed = await api.get(`${BACKEND_BASE}/api/v1/admin/users?offset=0&limit=500`, { headers });
    if (!refreshed.ok()) {
      throw new Error(`Failed to refresh users after invite: ${refreshed.status()} ${await refreshed.text()}`);
    }
    const payload = (await refreshed.json()) as AdminUserListResponse;
    user = payload.users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  }

  if (!user) throw new Error(`Could not resolve user after invite: ${email}`);

  const patchRes = await api.patch(`${BACKEND_BASE}/api/v1/admin/users/${user.id}`, {
    headers: { ...headers, "Content-Type": "application/json" },
    data: { role },
  });
  if (!patchRes.ok()) {
    throw new Error(`Failed to patch role for ${email}: ${patchRes.status()} ${await patchRes.text()}`);
  }
  return user.id;
}

async function ensureCredits(
  api: Awaited<ReturnType<typeof request.newContext>>,
  superToken: string,
  userId: number,
  email: string,
  targetCredits: number,
) {
  const headers = { Authorization: `Bearer ${superToken}` };
  const lookup = await api.get(`${BACKEND_BASE}/api/v1/admin/credits/user?query=${encodeURIComponent(email)}`, { headers });
  if (!lookup.ok()) {
    throw new Error(`Failed credit lookup ${email}: ${lookup.status()} ${await lookup.text()}`);
  }
  const payload = (await lookup.json()) as { credits?: { available_credits?: number } };
  const current = Number(payload.credits?.available_credits || 0);
  if (current >= targetCredits) return;
  const delta = Number((targetCredits - current).toFixed(2));
  const grant = await api.post(`${BACKEND_BASE}/api/v1/admin/credits/grant`, {
    headers: {
      ...headers,
      "Content-Type": "application/json",
      "Idempotency-Key": `e2e-seed-${email.replace(/[^a-z0-9]/gi, "-")}-${targetCredits}`,
    },
    data: { user_id: userId, credits: delta, reason: "E2E seed credits" },
  });
  if (!grant.ok()) {
    throw new Error(`Failed credit grant ${email}: ${grant.status()} ${await grant.text()}`);
  }
}

async function ensureLegalAcceptance(
  api: Awaited<ReturnType<typeof request.newContext>>,
  email: string,
) {
  const login = await loginAs(api, email, DEFAULT_PASSWORD);
  const headers = { Authorization: `Bearer ${login.access_token}`, "Content-Type": "application/json" };
  const statusRes = await api.get(`${BACKEND_BASE}/api/legal/status`, { headers });
  if (!statusRes.ok()) {
    throw new Error(`Failed legal status for ${email}: ${statusRes.status()} ${await statusRes.text()}`);
  }
  const status = (await statusRes.json()) as {
    latest_published?: {
      terms_of_service?: { version?: string };
      privacy_policy?: { version?: string };
    };
    latest_accepted?: {
      terms_of_service?: { version?: string } | null;
      privacy_policy?: { version?: string } | null;
    };
  };

  const latestTermsVersion = status.latest_published?.terms_of_service?.version;
  const latestPrivacyVersion = status.latest_published?.privacy_policy?.version;
  const acceptedTermsVersion = status.latest_accepted?.terms_of_service?.version;
  const acceptedPrivacyVersion = status.latest_accepted?.privacy_policy?.version;

  const accept = async (documentKey: "terms_of_service" | "privacy_policy", version: string) => {
    const res = await api.post(`${BACKEND_BASE}/api/legal/accept`, {
      headers,
      data: {
        document_key: documentKey,
        document_version: version,
        method: "in_app_modal",
      },
    });
    if (!res.ok()) {
      throw new Error(`Failed legal accept ${documentKey} for ${email}: ${res.status()} ${await res.text()}`);
    }
  };

  if (latestTermsVersion && acceptedTermsVersion !== latestTermsVersion) {
    await accept("terms_of_service", latestTermsVersion);
  }
  if (latestPrivacyVersion && acceptedPrivacyVersion !== latestPrivacyVersion) {
    await accept("privacy_policy", latestPrivacyVersion);
  }
}

async function seedBaselineLedger(
  api: Awaited<ReturnType<typeof request.newContext>>,
  userToken: string,
) {
  const check = await api.get(`${BACKEND_BASE}/api/v1/admin/credits/ledger?limit=5`, {
    headers: { Authorization: `Bearer ${userToken}` },
  });
  if (check.ok()) {
    const data = (await check.json()) as { items?: unknown[] };
    if ((data.items || []).length >= 5) return;
  }
}

export default async function globalSetup(_config: FullConfig) {
  const api = await request.newContext();
  try {
    const superEmail = seedUsers[0].email;
    const superLogin = await loginAs(api, superEmail, DEFAULT_PASSWORD);
    const superToken = superLogin.access_token;

    for (const u of seedUsers) {
      const userId = await ensureUser(api, superToken, u.email, u.name, u.role);
      await ensureCredits(api, superToken, userId, u.email, u.credits);
      if (!["superadmin", "admin", "support", "finance", "devops"].includes(u.role)) {
        await ensureLegalAcceptance(api, u.email);
      }
    }

    void _config;
    await seedBaselineLedger(api, superToken);
  } finally {
    await api.dispose();
  }
}
