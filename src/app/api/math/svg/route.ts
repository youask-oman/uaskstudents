import { NextResponse } from "next/server";
import { renderTexToSvg } from "@/lib/mathjax/renderSvg";

export const runtime = "nodejs";

type RequestBody = {
  tex?: string;
  display?: boolean;
};

const MAX_TEX_LENGTH = 20000;

export async function POST(req: Request) {
  let body: RequestBody;
  try {
    body = (await req.json()) as RequestBody;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const tex = String(body.tex ?? "").trim();
  const display = Boolean(body.display);

  if (!tex) {
    return NextResponse.json({ ok: false, error: "Missing tex." }, { status: 400 });
  }

  if (tex.length > MAX_TEX_LENGTH) {
    return NextResponse.json({ ok: false, error: "TeX too large." }, { status: 413 });
  }

  const result = renderTexToSvg(tex, { display });
  if (!result.ok) {
    return NextResponse.json(result, { status: 422 });
  }
  return NextResponse.json(result, { status: 200 });
}

