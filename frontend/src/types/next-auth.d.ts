import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    user?: DefaultSession['user'] & {
      id: string;
      role: 'User' | 'Admin';
      permissions: string[];
    };
  }
}