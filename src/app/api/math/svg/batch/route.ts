import { NextResponse } from "next/server";
import { renderTexToSvg } from "@/lib/mathjax/renderSvg";

export const runtime = "nodejs";

interface BatchItem {
  tex: string;
  display?: boolean;
}

interface RequestBody {
  items?: BatchItem[];
}

const MAX_ITEMS = 200;
const MAX_TEX_LENGTH = 20000;

export async function POST(req: Request) {
  let body: RequestBody;
  try {
    body = (await req.json()) as RequestBody;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const items = Array.isArray(body.items) ? body.items : [];

  if (items.length === 0) {
    return NextResponse.json({ ok: false, error: "No items provided." }, { status: 400 });
  }

  if (items.length > MAX_ITEMS) {
    return NextResponse.json({ ok: false, error: `Too many items (max ${MAX_ITEMS}).` }, { status: 413 });
  }

  const results = items.map((item) => {
    const tex = String(item.tex ?? "").trim();
    const display = Boolean(item.display);

    if (!tex) {
      return { ok: false, error: "Empty tex." };
    }

    if (tex.length > MAX_TEX_LENGTH) {
      return { ok: false, error: "TeX too large." };
    }

    return renderTexToSvg(tex, { display });
  });

  return NextResponse.json({ ok: true, results }, { status: 200 });
}
