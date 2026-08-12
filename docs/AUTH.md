# Authentication Mechanism

This document describes the authentication system.

## Overview

The application supports multiple authentication modes and providers that can be combined:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Application Modes                            │
├─────────────────────────────────────────────────────────────────────┤
│  MODE=development     │  MODE=production                            │
│  - No real auth       │  - Requires at least one provider OR        │
│  - Role switcher UI   │    USER_PASSWORDLESS=T                      │
│  - Mock users         │  - Real authentication                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Configuration (Environment Variables)

| Variable | Type | Description |
|----------|------|-------------|
| `MODE` | `development` \| `production` | Application mode |
| `AUTH_PROVIDER_AZURE` | `T/F` | Enable Azure AD / Entra ID SSO |
| `AUTH_PROVIDER_LOCAL_DB` | `T/F` | Enable email + password login |
| `AUTH_PROVIDER_MASTER_PW` | `T/F` | Enable master password login |
| `USER_PASSWORDLESS` | `T/F` | Enable passwordless user access |
| `MASTER_PASSWORD_ADMIN` | string | Password for admin role (required if `MASTER_PW=T`) |
| `MASTER_PASSWORD_USER` | string | Optional password for user role |

**Important**: Multiple providers can be enabled simultaneously!

## Authentication Providers

### 1. Development Mode (`MODE=development`)

- **No authentication required** - all users are auto-authenticated
- Role switcher in UI allows switching between `Admin` and `User` roles
- Mock user info: `dev@localhost`
- Stored in: `localStorage.dev_role`

### 2. Azure AD / Entra ID (`AUTH_PROVIDER_AZURE=T`)

**Flow:**
```
Frontend                    Azure AD                    Backend
   │                           │                           │
   │──loginRedirect()─────────>│                           │
   │                           │                           │
   │<──────callback + tokens───│                           │
   │                           │                           │
   │──POST /auth/azure-login {token}──────────────────────>│
   │                           │                           │
   │<──────────────{access_token, refresh_token}───────────│
```

- Uses MSAL (Microsoft Authentication Library) in frontend
- Token exchange: Azure token → Backend JWT
- Roles synced from Azure AD App Roles
- Logout redirects to Azure AD logout

### 3. Local Database (`AUTH_PROVIDER_LOCAL_DB=T`)

**Flow:**
```
Frontend                                    Backend
   │                                           │
   │──POST /auth/login {email, password}──────>│
   │                                           │
   │<──────{access_token, refresh_token}───────│
```

- Standard email/password authentication
- Users stored in `persons` table
- Password hashed with bcrypt

### 4. Master Password (`AUTH_PROVIDER_MASTER_PW=T`)

**Flow:**
```
Frontend                                    Backend
   │                                           │
   │──POST /auth/master-pw-login {password}───>│
   │                                           │
   │<──────{access_token, refresh_token}───────│
```

- Single shared password for admin access
- Optional secondary password for user access
- Creates/uses seed users in database

### 5. Passwordless (`USER_PASSWORDLESS=T`)

**Flow:**
```
Frontend                                    Backend
   │                                           │
   │──POST /auth/passwordless-token───────────>│
   │                                           │
   │<──────{access_token, refresh_token}───────│
```

- **No credentials required**
- Auto-grants `user` role to all visitors
- Used for public-facing apps where basic access is free
- Users can still "upgrade" to admin via other providers

## Token System

### Access Token
- JWT with claims: `sub` (user ID), `role`, `provider`
- Short-lived: `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30)
- Stored in: `localStorage.access_token`

### Refresh Token
- JWT with claim: `sub` (user ID)
- Long-lived: `REFRESH_TOKEN_EXPIRE_DAYS` (default: 7)
- Stored in: `localStorage.refresh_token`
- Endpoint: `POST /auth/refresh`

## Frontend State (Pinia Store: `auth.ts`)

### Key State Variables

```typescript
interface AuthState {
  authConfig: AuthConfig | null      // Config from /auth/config
  account: AccountInfo | null        // MSAL account (Azure)
  user: User | null                  // User from /auth/me
  accessToken: string | null         // JWT access token
  refreshToken: string | null        // JWT refresh token
  loginProvider: string | null       // 'azure' | 'local_db' | 'master_pw' | 'passwordless'
  isPasswordlessSession: boolean     // True if logged in via passwordless
  devRole: DevRole                   // 'Admin' | 'User' (dev mode only)
}
```

### Key Computed Properties

```typescript
isAuthenticated: boolean  // True if user can access protected routes
isDevelopmentMode: boolean
isProductionMode: boolean
isAdmin: boolean
currentRoles: LocalRole[]  // ['admin'] | ['user']
```

### Login Provider Tracking

The `loginProvider` state tracks how the user authenticated:
- `'azure'` - Azure AD login (logout will redirect to Azure)
- `'local_db'` - Email/password login
- `'master_pw'` - Master password login
- `'passwordless'` - Auto passwordless token
- `null` - Not logged in

**This is important for:**
1. Deciding whether to show logout button (hide for `passwordless`)
2. Deciding logout behavior (Azure redirects, others go to `/login`)
3. Showing "Anmelden" button (show when `passwordless` + not admin)

## Route Guards (`router/guards.ts`)

### Protected Route Flow

```
Route Navigation
      │
      ▼
┌─────────────────────┐
│ Is initialized?     │──No──> Initialize auth store
└─────────────────────┘
      │ Yes
      ▼
┌─────────────────────┐
│ requiresAuth: false │──Yes──> Allow access
└─────────────────────┘
      │ No
      ▼
┌─────────────────────┐
│ Development mode?   │──Yes──> Check roles, allow
└─────────────────────┘
      │ No
      ▼
┌─────────────────────┐
│ isAuthenticated?    │──Yes──> Check roles, allow
└─────────────────────┘
      │ No
      ▼
┌─────────────────────┐
│ Has stored token?   │──Yes──> Try loadUser(), check again
└─────────────────────┘
      │ No
      ▼
┌─────────────────────────────────┐
│ Azure + Passwordless active?   │──Yes──> Auto-trigger Azure login
└─────────────────────────────────┘
      │ No
      ▼
   Redirect to /login
```

## UI Behavior

### TopBar Component

| Condition | "Anmelden" Button | "Logout" Option |
|-----------|-------------------|-----------------|
| Development mode | Hidden | Hidden (can't logout) |
| Passwordless session (no admin) | **Shown** | Hidden |
| Passwordless session (admin) | Hidden | Shown |
| Other login (local_db, azure, master_pw) | Hidden | Shown |

### LoginSelector Component

Shows available login methods based on `authConfig.providers`:
- Azure: "Mit Microsoft anmelden" button
- Local DB: Email/password form
- Master PW: Password-only dialog

## Backend Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/config` | GET | Get auth configuration |
| `/auth/login` | POST | Local DB login |
| `/auth/azure-login` | POST | Azure token exchange |
| `/auth/master-pw-login` | POST | Master password login |
| `/auth/passwordless-token` | POST | Get passwordless token |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/logout` | POST | Logout (stateless - clears client side) |
| `/auth/me` | GET | Get current user info |

## Common Scenarios

### Scenario 1: Passwordless + Master Password

Config:
```env
USER_PASSWORDLESS=T
AUTH_PROVIDER_MASTER_PW=T
```

Behavior:
- All visitors auto-get `user` role
- "Anmelden" button shown for elevation
- Master password grants `admin` role
- Logout returns to passwordless state

### Scenario 2: Azure Only

Config:
```env
AUTH_PROVIDER_AZURE=T
```

Behavior:
- Unauthenticated users redirected to `/login`
- Login redirects to Azure
- Logout clears tokens + redirects to Azure logout

### Scenario 3: Multiple Providers

Config:
```env
AUTH_PROVIDER_AZURE=T
AUTH_PROVIDER_LOCAL_DB=T
USER_PASSWORDLESS=T
```

Behavior:
- Visitors auto-get passwordless token
- LoginSelector shows both Azure and email options
- User chooses preferred method
- `loginProvider` tracks which was used

## Key Files

### Frontend
- `src/stores/auth.ts` - Pinia auth store (main state management)
- `src/router/guards.ts` - Route protection logic
- `src/services/auth/authService.ts` - MSAL + auth utilities
- `src/components/auth/LoginSelector.vue` - Login UI
- `src/components/TopBar.vue` - Nav bar with login/logout
- `src/types/common.ts` - AuthConfig type definition

### Backend
- `app/config.py` - Settings with auth flags
- `app/api/v1/endpoints/auth.py` - Auth API endpoints
- `app/core/auth_factory.py` - Provider factory
- `app/core/auth_provider.py` - Base provider class
- `app/core/local_auth_provider.py` - Local DB provider
- `app/core/entra_auth_provider.py` - Azure provider
- `app/core/master_pw_auth_provider.py` - Master password provider
- `app/core/passwordless_auth_provider.py` - Passwordless provider
- `app/core/security.py` - JWT token creation/validation
