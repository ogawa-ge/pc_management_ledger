'use client';

import { signIn } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md">
        <Card className="shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-800">PC管理台帳</CardTitle>
            <CardDescription>Microsoftアカウントでログインしてください</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="flex justify-center">
              <Button
                onClick={() => signIn('azure-ad', { callbackUrl: '/pcs' })}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full"
              >
                Microsoftアカウントでログイン
              </Button>
            </div>
          </CardContent>
        </Card>
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>システムの利用規則に同意の上、ログインしてください</p>
        </div>
      </div>
    </div>
  );
}