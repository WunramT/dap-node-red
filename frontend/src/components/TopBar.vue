<template>
  <v-app-bar app color="secondary" elevation="1" height="64" fixed>
    <!-- Logo and Brand -->
    <div class="nav-brand clickable-brand" @click="$router.push('/')">
      <div class="app-logo">
        <v-icon size="32" color="primary">mdi-cube-outline</v-icon>
      </div>
      <v-divider vertical inset class="brand-divider" />
      <span class="app-title">dapnodered</span>
      <v-divider vertical inset class="ml-3 brand-divider" />
    </div>

    <!-- Navigation Menu (only show if authenticated) -->
    <template v-if="authStore.isAuthenticated">
      <v-btn text @click="$router.push('/')" class="nav-link">
        <v-icon start>mdi-home</v-icon>
        Home
      </v-btn>

      <!-- Add your navigation items here -->
      <!-- Example:
      <v-btn text @click="$router.push('/dashboard')" class="nav-link">
        <v-icon start>mdi-view-dashboard</v-icon>
        Dashboard
      </v-btn>
      -->

      <!-- Admin Menu (for admin only) -->
      <v-menu v-if="authStore.isAdmin">
        <template #activator="{ props }">
          <v-btn text v-bind="props" class="nav-link">
            <v-icon start>mdi-cog</v-icon>
            Administration
            <v-icon end>mdi-menu-down</v-icon>
          </v-btn>
        </template>

        <v-list>
          <!-- Add admin menu items here -->
          <!-- Example:
          <v-list-item
            prepend-icon="mdi-account-group"
            title="User Management"
            @click="$router.push('/admin/users')"
          ></v-list-item>
          -->
          <v-list-item
            prepend-icon="mdi-information"
            title="System Info"
            @click="showSystemInfo"
          ></v-list-item>
        </v-list>
      </v-menu>
    </template>

    <v-spacer />

    <!-- Dev Mode Role Switcher (only in development mode) -->
    <div v-if="isDevelopmentMode" class="dev-mode-switcher mr-4">
      <v-chip color="warning" size="small" class="mr-2">DEV MODE</v-chip>
      <v-select
        v-model="selectedDevRole"
        :items="devRoleOptions"
        item-title="label"
        item-value="value"
        density="compact"
        variant="outlined"
        hide-details
        class="dev-role-select"
        @update:model-value="onDevRoleChange"
      />
    </div>

    <!-- Passwordless "Anmelden" button (production + passwordless + no elevated role) -->
    <v-btn
      v-if="isPasswordlessModeActive && !authStore.isAdmin"
      color="primary"
      variant="outlined"
      class="mr-3"
      prepend-icon="mdi-login"
      @click="showLoginDialog = true"
    >
      Anmelden
    </v-btn>

    <!-- Login Dialog for elevated access in passwordless mode -->
    <v-dialog v-model="showLoginDialog" max-width="500" persistent>
      <LoginSelector @close="showLoginDialog = false" />
    </v-dialog>

    <!-- User Profile (only show if authenticated) -->
    <v-menu v-if="authStore.isAuthenticated">
      <template #activator="{ props }">
        <v-btn icon v-bind="props" class="user-btn">
          <v-avatar color="primary" size="36">
            <span class="text-h6 text-white">{{ userInitials }}</span>
          </v-avatar>
        </v-btn>
      </template>

      <v-list>
        <v-list-item>
          <v-list-item-title>{{ authStore.userName }}</v-list-item-title>
          <v-list-item-subtitle>{{ authStore.userEmail }}</v-list-item-subtitle>
        </v-list-item>
        <template v-if="canLogout">
          <v-divider></v-divider>
          <v-list-item
            prepend-icon="mdi-logout"
            title="Logout"
            @click="handleLogout"
          ></v-list-item>
        </template>
      </v-list>
    </v-menu>
  </v-app-bar>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAuthStore, type DevRole } from '@/stores/auth'
import { useUiStore } from '@/stores/uiStore'
import LoginSelector from '@/components/auth/LoginSelector.vue'

const authStore = useAuthStore()
const uiStore = useUiStore()

// Dev mode state
const isDevelopmentMode = computed(() => authStore.isDevelopmentMode)

// Passwordless: production mode AND passwordless is enabled in config AND logged in via passwordless (not elevated)
const isPasswordlessModeActive = computed(() =>
  authStore.isProductionMode &&
  authStore.authConfig?.passwordless &&
  authStore.loginProvider === 'passwordless'
)

// Check if user can logout (not in pure passwordless session)
const canLogout = computed(() =>
  authStore.loginProvider !== 'passwordless'
)

const showLoginDialog = ref(false)

const devRoleOptions = [
  { value: 'Admin', label: 'Admin' },
  { value: 'User', label: 'User' },
]

const selectedDevRole = ref<DevRole>(authStore.devRole)

// Watch for external changes to devRole
watch(
  () => authStore.devRole,
  (newRole) => {
    selectedDevRole.value = newRole
  }
)

// Computed
const userInitials = computed(() => {
  const name = authStore.userName
  if (!name) return '?'
  const parts = name.split(' ')
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  }
  return name.substring(0, 2).toUpperCase()
})

// Methods
function onDevRoleChange(role: DevRole) {
  authStore.switchDevRole(role)
  // Reload the page to ensure all data is refreshed
  window.location.reload()
}

function handleLogout() {
  authStore.logout()
}

function showSystemInfo() {
  uiStore.showInfo('System info: Check /api/health endpoint')
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as vars;

// Navigation Brand
.nav-brand {
  display: flex;
  align-items: center;
  padding-left: 16px;
  gap: 16px;

  &.clickable-brand {
    cursor: pointer;
    transition: opacity 0.2s ease;

    &:hover {
      opacity: 0.8;
    }
  }

  .app-logo {
    height: 48px;
    width: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: white;
    border-radius: 8px;
    box-shadow: vars.$shadow-sm;
  }

  .app-title {
    font-size: 20px;
    font-weight: 500;
    color: vars.$color-text-nav;
    letter-spacing: -0.02em;
    white-space: nowrap;
    transition: color 0.2s ease;

    &:hover {
      color: vars.$color-text-white;
    }
  }

  .brand-divider {
    opacity: 0.3;
    border-color: vars.$color-text-nav !important;
  }

  :deep(.v-divider) {
    height: 32px;
    align-self: center;

    &:last-child {
      margin-left: 12px !important;
    }
  }
}

// Navigation Links
.nav-link {
  text-transform: none !important;
  color: vars.$color-text-nav !important;
  margin: 0 4px;
  transition: all 0.2s ease;

  &:hover {
    color: vars.$color-text-nav-hover !important;
    background-color: rgba(255, 255, 255, 0.1) !important;
  }

  &.router-link-active,
  &.v-btn--active {
    color: vars.$color-text-nav-active !important;
    background-color: rgba(vars.$color-primary, 0.1) !important;
  }
}

// User Button
.user-btn {
  color: vars.$color-text-nav !important;

  &:hover {
    background-color: rgba(255, 255, 255, 0.1) !important;
  }
}

// Override Vuetify AppBar styles
:deep(.v-field) {   background-color: rgba(255, 255, 255, 0.15) !important; }

// Dev Mode Switcher
.dev-mode-switcher {
  display: flex;
  align-items: center;
  gap: 8px;

  .dev-role-select {
    width: 120px;
    border-radius: 4px;
    :deep(.v-field) {
      background-color: rgba(255, 255, 255, 0.15) !important;
    }

    :deep(.v-field__input) {
      font-size: 13px;
      min-height: 32px;
      padding: 4px 8px;
    }

    :deep(.v-field__outline) {
      --v-field-border-opacity: 0.3;
    }
  }
}

// Mobile Responsive
@media (max-width: 960px) {
  .nav-brand {
    padding-left: 8px;
    gap: 8px;

    .app-title {
      font-size: 18px;
    }

    .brand-divider {
      display: none !important;
    }
  }
}

@media (max-width: 600px) {
  .nav-brand {
    .app-title {
      display: none;
    }

    .app-logo {
      height: 36px;
      width: 36px;
    }
  }
}
</style>
