export interface PC {
  id: string;
  name: string;
  os: string;
  cpu: string;
  memory: string;
  storage: string;
  gpu?: string;
  status: 'available' | 'assigned' | 'returned' | 'maintenance';
  assignedUserId?: string;
  createdAt: string;
  updatedAt: string;
}