export interface PC {
  pcId: string;
  ownerId?: string | null;
  ownerName?: string | null;
  type: string;
  status: 'InUse' | 'Unused' | 'PendingDisposal' | 'Disposed';
  pcName?: string | null;
  cpu?: string | null;
  memory?: string | null;
  storage?: string | null;
  os?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  gpu?: string | null;
  serialNumber?: string | null;
  createdAt: string;
  updatedAt: string;
}