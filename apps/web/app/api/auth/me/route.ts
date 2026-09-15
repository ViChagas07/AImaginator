import {NextRequest, NextResponse} from "next/server";
import {API_BASE_URL} from "@/lib/constants";

export async function GET(req: NextRequest) {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: {
      cookie: req.headers.get("cookie") ?? "",
    },
    cache: "no-store",
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {"content-type": "application/json"},
  });
}
