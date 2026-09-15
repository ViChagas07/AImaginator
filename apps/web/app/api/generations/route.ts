import {NextRequest, NextResponse} from "next/server";
import {API_BASE_URL} from "@/lib/constants";

function headersFrom(req: NextRequest) {
  const cookie = req.headers.get("cookie");
  const headers: Record<string, string> = {};
  if (cookie) headers.cookie = cookie;
  return headers;
}

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await fetch(`${API_BASE_URL}/api/v1/generations`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...headersFrom(req),
    },
    body,
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {"content-type": "application/json"},
  });
}

export async function GET(req: NextRequest) {
  const url = new URL(req.nextUrl.toString());
  const cursor = url.searchParams.get("cursor");
  const target = new URL(`${API_BASE_URL}/api/v1/generations`);
  if (cursor) target.searchParams.set("cursor", cursor);
  const res = await fetch(target, {
    headers: headersFrom(req),
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {"content-type": "application/json"},
  });
}
