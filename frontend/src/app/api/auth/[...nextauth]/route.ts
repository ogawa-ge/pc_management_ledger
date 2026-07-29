import NextAuth from 'next-auth';
import AzureADProvider from 'next-auth/providers/azure-ad';
import { get_user_auth_info } from '@/lib/auth-service';

export const authOptions = {
  providers: [
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      tenantId: process.env.AZURE_AD_TENANT_ID!,
    }),
  ],
  callbacks: {
    async jwt({ token, account }: any) {
      // Access tokenをJWTに追加
      if (account) {
        token.accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }: any) {
      // セッションにアクセストークンを追加
      session.accessToken = token.accessToken;
      // JWTトークンからユーザーIDを取得し、権限とロールを取得してセッションに追加
      if (token && token.sub) {
        try {
          const authInfo = await get_user_auth_info(token.sub);
          session.user = {
            ...session.user,
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