import {NextRequest, NextResponse} from "next/server";
import {API_BASE_URL} from "@/lib/constants";

export async function GET(req: NextRequest) {
  const cursor = req.nextUrl.searchParams.get("cursor");
  const target = new URL(`${API_BASE_URL}/api/v1/gallery/public`);
  if (cursor) target.searchParams.set("cursor", cursor);
  const res = await fetch(target, {cache: "no-store"});
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {"content-type": "application/json"},
  });
}
