import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    accessToken?: string;
    user?: DefaultSession['user'] & {
      id: string;
      role: 'User' | 'Admin';
      permissions: string[];
    };
  }
}