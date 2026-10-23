import NextAuth, { AuthOptions } from 'next-auth';
import GoogleProvider, { GoogleProfile } from 'next-auth/providers/google';
import { get_user_auth_info, syncUser } from '@/lib/auth-service';
import { getRejectionReason } from '@/lib/email-domain';

export const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      // アカウント選択画面を許可ドメインに絞り込む（使い勝手のためで、ログイン可否の判定には使わない）
      authorization: { params: { hd: process.env.ALLOWED_EMAIL_DOMAIN } },
    }),
  ],
  pages: {
    signIn: '/login',
    error: '/login',
  },
  callbacks: {
    async signIn({ profile: rawProfile }) {
      const profile = rawProfile as GoogleProfile | undefined;

      // 許可ドメイン以外のアカウントは、ユーザー登録より前に拒否する
      const rejectionReason = getRejectionReason(
        { email: profile?.email, emailVerified: profile?.email_verified, hostedDomain: profile?.hd },
        process.env.ALLOWED_EMAIL_DOMAIN ?? ''
      );
      if (rejectionReason) {
        console.warn(
          JSON.stringify({
            event: 'login_rejected',
            reason: rejectionReason,
            email: profile?.email ?? '',
            timestamp: new Date().toISOString(),
            source: 'frontend',
          })
        );
        return '/login?error=DomainNotAllowed';
      }

      // Google の sub を userId として Users に登録する（token.sub にも sub が入る）
      try {
        await syncUser({
          userId: profile?.sub ?? '',
          email: profile?.email ?? '',
          name: profile?.name,
        });
        return true;
      } catch (error) {
        console.error('ユーザー登録に失敗しました:', error);
        return '/login?error=RegistrationFailed';
      }
    },
    async session({ session, token }: any) {
      // JWTトークンからユーザーIDを取得し、権限とロールを取得してセッションに追加
      if (token && token.sub) {
        try {
          const authInfo = await get_user_auth_info(token.sub);
          session.user = {
            ...session.user,
            id: token.sub,
            permissions: authInfo.permissions,
            role: authInfo.role,
          };
        } catch (error) {
          console.error('認証情報の取得に失敗しました:', error);
        }
      }
      return session;
    },
  },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
