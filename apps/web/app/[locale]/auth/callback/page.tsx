"use client";

import {useEffect} from "react";
import {parseSessionFromHash, saveSession} from "@/lib/auth-token";

export default function AuthCallbackPage() {
  useEffect(() => {
    const session = parseSessionFromHash(window.location.hash);
    if (session) saveSession(session);
    window.location.replace("/pt-BR/studio");
  }, []);

  return null;
}
