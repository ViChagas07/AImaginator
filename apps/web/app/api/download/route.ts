import {NextRequest, NextResponse} from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const STORAGE_ORIGIN = (process.env.NEXT_PUBLIC_STORAGE_ORIGIN ?? "").replace(
  /\/+$/,
  "",
);

export async function GET(req: NextRequest) {
  const rawUrl = req.nextUrl.searchParams.get("url");
  if (!rawUrl) {
    return NextResponse.json({error: "url obrigatoria"}, {status: 400});
  }

  let target: URL;
  try {
    target = new URL(rawUrl);
  } catch {
    return NextResponse.json({error: "url invalida"}, {status: 400});
  }
  if (target.protocol !== "http:" && target.protocol !== "https:") {
    return NextResponse.json({error: "protocolo invalido"}, {status: 400});
  }
  if (!STORAGE_ORIGIN) {
    return NextResponse.json(
      {error: "storage nao configurado"},
      {status: 503},
    );
  }
  let allowed: URL;
  try {
    allowed = new URL(STORAGE_ORIGIN);
  } catch {
    return NextResponse.json(
      {error: "storage nao configurado"},
      {status: 503},
    );
  }
  if (target.origin !== allowed.origin) {
    return NextResponse.json({error: "origem nao permitida"}, {status: 400});
  }

  try {
    const upstream = await fetch(target, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (!upstream.ok) {
      return NextResponse.json(
        {error: "falha ao buscar a imagem"},
        {status: 502},
      );
    }
    const contentType = upstream.headers.get("content-type") ?? "";
    if (!contentType.startsWith("image/")) {
      return NextResponse.json(
        {error: "conteudo nao e imagem"},
        {status: 502},
      );
    }
    const filename = (req.nextUrl.searchParams.get("filename") ?? "aimaginator.png")
      .replace(/[^a-zA-Z0-9._-]/g, "-")
      .slice(0, 120);
    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: 200,
      headers: {
        "content-type": contentType,
        "content-length": String(body.byteLength),
        "content-disposition": `attachment; filename="${filename}"`,
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  } catch {
    return NextResponse.json(
      {error: "falha ao baixar a imagem"},
      {status: 502},
    );
  }
}
