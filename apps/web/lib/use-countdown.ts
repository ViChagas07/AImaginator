import {useEffect, useState} from "react";

export function useCountdown(targetIso: string | null): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!targetIso) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  if (!targetIso) return 0;
  return Math.max(0, Math.ceil((new Date(targetIso).getTime() - now) / 1000));
}
