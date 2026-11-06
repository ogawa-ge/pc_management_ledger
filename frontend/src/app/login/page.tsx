'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const LOGIN_FAILED_MESSAGE = 'ログインに失敗しました。しばらくしてから再度お試しください';
const DOMAIN_NOT_ALLOWED_MESSAGE = '会社のGoogleアカウントでログインしてください';

const getLoginErrorMessage = (error: string | null): string | null => {
  if (!error) {
    return null;
  }
  if (error === 'DomainNotAllowed') {
    return DOMAIN_NOT_ALLOWED_MESSAGE;
  }
  return LOGIN_FAILED_MESSAGE;
};

function LoginErrorMessage() {
  const searchParams = useSearchParams();
  const errorMessage = getLoginErrorMessage(searchParams.get('error'));

  if (!errorMessage) {
    return null;
  }

  return (
    <p role="alert" className="mb-4 rounded bg-red-50 p-3 text-center text-sm text-red-700">
      {errorMessage}
    </p>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md">
        <Card className="shadow-lg">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-800">PC管理台帳</CardTitle>
            <CardDescription>会社のGoogleアカウントでログインしてください</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <Suspense fallback={null}>
              <LoginErrorMessage />
            </Suspense>
            <div className="flex justify-center">
              <Button
                onClick={() => signIn('google', { callbackUrl: '/pcs' })}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full"
              >
                Googleアカウントでログイン
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
