'use client';

import { createContext, useContext, type ReactNode } from 'react';

const DemoAccess = createContext(false);

export function DemoAccessProvider({ readOnly, children }: { readOnly: boolean; children: ReactNode }) {
  return <DemoAccess.Provider value={readOnly}>{children}</DemoAccess.Provider>;
}

export function useReadOnlyDemo() {
  return useContext(DemoAccess);
}
