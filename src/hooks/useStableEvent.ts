"use client";

import { useCallback, useEffect, useRef } from "react";

export function useStableEvent<T extends (...args: never[]) => unknown>(handler: T): T {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  const stableHandler = useCallback((...args: Parameters<T>) => handlerRef.current(...args), []);
  return stableHandler as T;
}
