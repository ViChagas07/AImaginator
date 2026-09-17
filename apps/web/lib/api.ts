import {API_BASE_URL} from "@/lib/constants";
import {getAccessToken, getRefreshToken, saveSession} from "@/lib/auth-token";

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({refresh_token: refresh}),
      cache: "no-store",
    });
    if (!res.ok) return false;
    const data = (await res.json()) as {access_token?: string};
    if (data.access_token) {
      saveSession({access_token: data.access_token, refresh_token: refresh});
      return true;
    }
  } catch {
    // rede/API indisponível — mantém o token atual
  }
  return false;
}

export async function authedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(input, {...init, headers});
  if (res.status === 401 && getRefreshToken()) {
    if (await refreshAccessToken()) {
      const newToken = getAccessToken();
      if (newToken) {
        headers.set("Authorization", `Bearer ${newToken}`);
        return fetch(input, {...init, headers});
      }
    }
  }
  return res;
}
