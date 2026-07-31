import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TOKEN_ENDPOINT =
  "https://mp.speechmatics.com/v1/api_keys?type=rt";
const TOKEN_TTL_SECONDS = 60;

function requestIsSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");

  if (!origin || !host) {
    return true;
  }

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  if (!requestIsSameOrigin(request)) {
    return NextResponse.json(
      {
        detail: "Cross-origin token requests are not allowed.",
      },
      {
        status: 403,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const apiKey =
    process.env.SPEECHMATICS_API_KEY?.trim();

  if (!apiKey) {
    return NextResponse.json(
      {
        detail: "Speechmatics is not configured.",
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  try {
    const response = await fetch(TOKEN_ENDPOINT, {
      method: "POST",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ttl: TOKEN_TTL_SECONDS,
      }),
    });

    const payload = await response
      .json()
      .catch(() => ({}));

    if (
      !response.ok
      || typeof payload.key_value !== "string"
      || !payload.key_value
    ) {
      console.error(
        "[SPEECHMATICS TOKEN ERROR]",
        `status=${response.status}`,
      );

      return NextResponse.json(
        {
          detail:
            "Speechmatics temporary authorization is unavailable.",
        },
        {
          status: 502,
          headers: {
            "Cache-Control": "no-store",
          },
        },
      );
    }

    return NextResponse.json(
      {
        token: payload.key_value,
        expires_in: TOKEN_TTL_SECONDS,
        token_type: "realtime-temporary-key",
      },
      {
        status: 200,
        headers: {
          "Cache-Control":
            "no-store, no-cache, must-revalidate",
          Pragma: "no-cache",
        },
      },
    );
  } catch (error) {
    console.error(
      "[SPEECHMATICS TOKEN ERROR]",
      error instanceof Error
        ? error.name
        : "UnknownError",
    );

    return NextResponse.json(
      {
        detail:
          "Speechmatics temporary authorization is unavailable.",
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
