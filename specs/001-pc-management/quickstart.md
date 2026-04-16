# Quickstart

## Prerequisites
- Node.js 18+
- Python 3.11+
- AWS CLI configured with appropriate credentials
- Docker (for local ECS testing)
- Gemini API Key

## Local Development Setup

1. **Frontend (Next.js)**
   ```bash
   cd frontend
   npm install
   # .env.local に必要な環境変数を設定 (NEXTAUTH_URL, AZURE_AD_CLIENT_ID, etc.)
   npm run dev
   ```

2. **Backend (Lambda - Login API)**
   ```bash
   cd backend/lambda
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   # ローカル実行用のスクリプトまたはAWS SAM等を利用
   ```

3. **Backend (ECS - Core API)**
   ```bash
   cd backend/ecs
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   # .env に GEMINI_API_KEY 等を設定
   uvicorn src.main:app --reload --port 8000
   ```

4. **Infrastructure (CDK)**
   ```bash
   cd infrastructure
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cdk synth
   ```
