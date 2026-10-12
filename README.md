# Face Authentication and Customer Transaction System
## Phase 1: Project Setup and Admin Authentication

A production-grade, secure authentication foundation for the Face Authentication & Customer Transaction System.

---

## 1. System Architecture Overview

Phase 1 establishes the operational core and single-admin role authentication:

- **Frontend (`frontend/`)**: Built with **SvelteKit (JavaScript only, strictly no TypeScript)**. Clean, responsive UI implementing the exact design system palette (Forest, Terracotta, Cream, White, Gray).
- **Backend (`backend/`)**: Built with **Python FastAPI**. Manages secure server-side operations, CORS policies, environment configurations, and Bearer token verification.
- **Authentication**: **Firebase Authentication** with persistent browser session handling for the operational `ADMIN` account. Public user registration is strictly blocked.
- **Database**: **Cloud Firestore** secured with strict security rules that deny public access by default and allow only authenticated admin access.
- **Email Service**: **Gmail SMTP** (`smtp.gmail.com:587` with STARTTLS) configured exclusively on the server side using Python's built-in `smtplib` and `email.message` for OTP verification and customer card issuance notifications without third-party dependencies.

```
Face ATM/
├── .env.example              # Master environment variables template
├── .gitignore                # Excludes secrets, keys, and dependencies
├── firestore.rules           # Cloud Firestore admin security rules
├── README.md                 # Complete system guide & setup instructions
├── backend/
│   ├── .env.example          # Backend-specific environment variables
│   ├── requirements.txt      # Python dependencies (FastAPI, Firebase Admin)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI entrypoint, CORS & error handling
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py     # Pydantic Settings environment configuration
│   │   │   ├── firebase.py   # Firebase Admin SDK & token validation
│   │   │   └── security.py   # FastAPI dependency for admin verification
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── email_service.py # Gmail SMTP email service & health probe
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py     # Health & system status endpoints
│   │       └── admin.py      # Protected admin verify & placeholder metrics
│   └── scripts/
│       └── create_admin.py   # CLI provisioning tool for initial admin account
└── frontend/
    ├── .env.example          # Frontend-specific environment variables
    ├── package.json          # SvelteKit + Firebase dependencies
    ├── svelte.config.js
    ├── vite.config.js
    ├── src/
    │   ├── app.html          # Base HTML document with viewport settings
    │   ├── app.css           # Global CSS design tokens & palette styling
    │   ├── lib/
    │   │   ├── index.js      # Library exports
    │   │   ├── firebase.js   # Firebase Client SDK & persistent auth helpers
    │   │   └── auth.js       # Svelte auth store & user-friendly error mapping
    │   └── routes/
    │       ├── +layout.svelte        # Root layout initializing auth state
    │       ├── +page.svelte          # Root redirector (/ -> /admin/dashboard or /login)
    │       ├── login/
    │       │   └── +page.svelte      # Admin login page with password toggle & validation
    │       └── admin/
    │           ├── +layout.svelte    # Protected route guard & sidebar navigation
    │           ├── +page.svelte      # Redirects /admin to /admin/dashboard
    │           └── dashboard/
    │               └── +page.svelte  # Admin dashboard with 0-value placeholder cards
```

---

## 2. Color Palette & Design Tokens

The application strictly implements the required color palette:

| Token Name | Hex Code | Visual Role |
| :--- | :--- | :--- |
| **Forest** | `#173F35` | Primary brand color, headers, sidebar background |
| **Terracotta** | `#D97745` | Primary call-to-action buttons, active badges, accents |
| **Cream** | `#F5EFE6` | Page background, cards surface, secondary elements |
| **White** | `#FFFFFF` | Form surfaces, dashboard metric cards, high-contrast text |
| **Gray** | `#66736F` | Secondary labels, icon borders, placeholder tags |

---

## 3. Step-by-Step Setup Guide

### Step 3.1: Firebase Project Setup

1. **Create a Firebase Project:**
   - Navigate to the [Firebase Console](https://console.firebase.google.com/).
   - Click **Add project** and name it (e.g., `face-atm-system`).
   - Disable Google Analytics for this development environment (optional) and click **Create Project**.

2. **Enable Email/Password Authentication:**
   - In the Firebase Console left navigation, select **Build > Authentication**.
   - Click **Get Started**.
   - Under the **Sign-in method** tab, click **Email/Password**.
   - Toggle **Enable** for Email/Password and click **Save**. *(Do not enable Email link/passwordless).*

3. **Configure Cloud Firestore:**
   - In the left navigation, select **Build > Firestore Database**.
   - Click **Create Database**.
   - Choose a Firestore location close to your region (e.g., `nam5` or `eur3`).
   - Start in **Production mode** (denies public read/write by default).
   - Under the **Rules** tab, deploy the rules provided in `firestore.rules`.

4. **Register Web App & Obtain Public Client Configuration:**
   - In the Firebase Console, click the **Gear Icon (Project settings)** > **General**.
   - Scroll down to **Your apps** and click the **Web icon (`</>`)**.
   - Register app with nickname `Face ATM Frontend`.
   - Copy the `firebaseConfig` object values for your frontend environment variables.

5. **Generate Service Account Credentials for Backend:**
   - In **Project settings**, navigate to the **Service accounts** tab.
   - Click **Generate new private key**, then click **Generate key**.
   - Save the downloaded JSON file securely inside `backend/` as `serviceAccountKey.json`.
   - *(Note: `serviceAccountKey.json` is already excluded in `.gitignore` to prevent credential exposure).*

---

### Step 3.2: Gmail SMTP Email Configuration

The system uses standard Python `smtplib` and `email.message` to send one-time passcodes (OTPs) and card activation notifications via Gmail SMTP with TLS (`smtp.gmail.com:587`).

1. **Enable 2-Step Verification & Generate Google App Password:**
   - Log into your Google Account: [https://myaccount.google.com/security](https://myaccount.google.com/security).
   - Ensure **2-Step Verification** is enabled.
   - Go to **App Passwords**: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   - Create a new App Password named `Face ATM`.
   - Copy the generated 16-character string (e.g., `abcd efgh ijkl mnop`).

2. **Configure Backend `.env`:**
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=pavithra.workss@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   SMTP_FROM=pavithra.workss@gmail.com
   ```
   > ⚠️ **Important Security Notice:**
   > - Use your generated **16-character Google App Password**, NOT your personal Google login password.
   > - Never commit `.env` or expose `SMTP_PASSWORD` to the frontend client.

3. **SMTP Troubleshooting:**
   - **`535 5.7.8 Username and Password not accepted`**: Check that 2-Step Verification is ON and you are using a 16-character App Password without typos.
   - **Connection timed out / refused**: Ensure outbound traffic on port 587 (TCP) is not blocked by local firewalls or VPNs.
   - **Test Connection Tool**: Administrators can test SMTP connectivity via the backend endpoint `POST /api/admin/test-smtp`.

---

### Step 3.3: Environment Variables Configuration

Copy `.env.example` in both root/frontend and backend directories:

#### Frontend (`frontend/.env`)
```bash
cp frontend/.env.example frontend/.env
```
Populate with your Firebase Web App configuration:
```env
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=face-atm-system.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=face-atm-system
VITE_FIREBASE_STORAGE_BUCKET=face-atm-system.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=1234567890
VITE_FIREBASE_APP_ID=1:1234567890:web:abcdef
VITE_BACKEND_API_URL=http://localhost:8000
```

#### Backend (`backend/.env`)
```bash
cp backend/.env.example backend/.env
```
Populate backend environment variables:
```env
HOST=127.0.0.1
PORT=8000
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Designated Operational Admin Email
ADMIN_EMAIL=admin@faceatm.local

# Path to downloaded Firebase service account key
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=serviceAccountKey.json
FIREBASE_PROJECT_ID=face-atm-system

# Gmail SMTP Email Configuration (Kept strictly on server)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=pavithra.workss@gmail.com
SMTP_PASSWORD=YOUR_16_CHAR_GOOGLE_APP_PASSWORD
SMTP_FROM=pavithra.workss@gmail.com
```


---

### Step 3.4: Provisioning the Operational Admin Account

Public registration is disabled. You must provision the system administrator using the provided secure server script:

```bash
# In backend directory with virtual environment activated:
python scripts/create_admin.py --email admin@faceatm.local
```
- The script securely prompts for a password via masked input (`getpass`).
- Provisions the account in Firebase Authentication.
- Grants custom claim `{"admin": True}` to verify admin role on token decode.
- Creates an authorized document in `/admins/{uid}` in Cloud Firestore.

---

## 4. Execution & Running Locally

### Step 4.1: Running the FastAPI Backend

1. **Activate Python Virtual Environment & Install Dependencies:**
   ```bash
   cd backend
   python -m venv venv
   
   # Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # macOS / Linux:
   # source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Start the FastAPI Server:**
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   - API Root: `http://127.0.0.1:8000/`
   - Health Status: `http://127.0.0.1:8000/api/health`
   - Interactive Swagger Docs: `http://127.0.0.1:8000/docs`

---

### Step 4.2: Running the SvelteKit Frontend

1. **Install Dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start Vite Dev Server:**
   ```bash
   npm run dev
   ```
   - Open browser at `http://localhost:5173`

---

## 5. Security & Verification Rules

1. **Protected Admin Routes**: 
   - Visiting `/admin` or `/admin/dashboard` while unauthenticated immediately redirects to `/login`.
   - Logging in with invalid credentials displays specific error notifications.
   - Successful login persists session locally via Firebase Auth `browserLocalPersistence`.
2. **Server-Side Authorization**:
   - Administrative endpoints (`/api/admin/verify`, `/api/admin/summary`) reject requests lacking a valid Firebase Bearer token with HTTP `401 Unauthorized`.
   - Tokens not matching `ADMIN_EMAIL` or missing `admin: true` claims are rejected with HTTP `403 Forbidden`.
3. **Firestore Protection**:
   - `firestore.rules` enforces that non-admin requests are completely rejected (`allow read, write: if false;`).
4. **Phase 1 Metrics Scope**:
   - Dashboard cards display `0 Registered Customers`, `0 Face Verifications`, `0 Completed Transactions`.
   - Clearly labeled as placeholders pending Phase 2 biometric and Phase 3 transaction workflows.

---

## 6. API Reference

| Endpoint | Method | Security | Description |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | Public | Service greeting and Phase 1 online status |
| `/api/health` | `GET` | Public | Component readiness (API, Firebase Admin, Gmail SMTP without secrets) |
| `/api/admin/verify` | `GET` | Bearer Token (Admin) | Validates Firebase ID token and admin privilege |
| `/api/admin/summary` | `GET` | Bearer Token (Admin) | Returns Phase 1 & 2 dashboard metric counts |
| `/api/admin/test-smtp` | `POST` | Bearer Token (Admin) | Safely probes Gmail SMTP connection and authentication |
#   F A C E - A T M - A N A L Y S I S  
 