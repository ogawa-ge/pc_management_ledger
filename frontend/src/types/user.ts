export interface User {
  userId: string;
  name?: string;
  email?: string;
  role: 'User' | 'Admin';
  createdAt?: string;
  updatedAt?: string;
}
