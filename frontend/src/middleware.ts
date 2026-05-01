import { NextResponse } from 'next/server';
import { getToken } from 'next-auth/jwt';

// 認証ミドルウェアの実装
export default async function middleware(request: any) {
  const token = await getToken({ req: request, secret: process.env.NEXTAUTH_SECRET });
  
  // 認証されていない場合、ログインページにリダイレクト
  if (!token && request.nextUrl.pathname !== '/login') {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    return NextResponse.redirect(url);
  }
  
  // 認証されている場合、通常の処理を継続
  return NextResponse.next();
}

// ミドルウェアのパスマッチング
export const config = {
  matcher: [
    /*
     * ミドルウェアを適用するパスのマッチパターンを定義
     * 例: '/(api|auth|dashboard)/(.*)'
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};