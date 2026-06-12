export interface PC {
  pcId: string;
  ownerId: string;
  ownerName?: string;
  type: string;
  status: 'InUse' | 'Unused' | 'PendingDisposal' | 'Disposed';
  cpu?: string;
  memory?: string;
  storage?: string;
  os?: string;
  manufacturer?: string;
  model: string;
  modelName?: string;
  serialNumber?: string;
  createdAt: string;
  updatedAt: string;
}