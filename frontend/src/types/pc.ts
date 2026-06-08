export interface PC {
  pcId: string;
  pc_id?: string;
  ownerId: string;
  owner_id?: string;
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
  serial_number?: string;
  createdAt: string;
  created_at?: string;
  updatedAt: string;
  updated_at?: string;
}