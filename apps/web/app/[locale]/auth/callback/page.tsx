"use client";

import {useEffect} from "react";
import {useRouter} from "@/i18n/navigation";
import {parseSessionFromHash} from "@/lib/auth-token";
import {useAuthStore} from "@/stores/auth";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const session = parseSessionFromHash(window.location.hash);
    if (session) {
      void useAuthStore
        .getState()
        .completeAuth(session)
        .finally(() => router.replace("/"));
    } else {
      router.replace("/login");
    }
  }, [router]);

  return null;
}
