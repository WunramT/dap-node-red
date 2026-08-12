<template>
  <v-container fluid class="pa-6">
    <v-row justify="center">
      <v-col cols="12" md="8" lg="6">
        <v-card class="text-center pa-8" elevation="4">
          <v-icon
            icon="mdi-rocket-launch"
            size="80"
            color="primary"
            class="mb-4"
          ></v-icon>

          <h1 class="text-h3 mb-4">Welcome to dapnodered</h1>

          <p class="text-body-1 text-medium-emphasis mb-6">
            Your application is running successfully!
            This is a template project ready for customization.
          </p>

          <v-divider class="my-6"></v-divider>

          <div class="d-flex flex-column align-center">
            <h2 class="text-h6 mb-4">Quick Links</h2>

            <div class="d-flex flex-wrap gap-3 justify-center">
              <v-btn
                color="primary"
                prepend-icon="mdi-file-document"
                href="/api/docs"
                target="_blank"
              >
                API Documentation
              </v-btn>

              <v-btn
                color="secondary"
                prepend-icon="mdi-heart-pulse"
                href="/api/health"
                target="_blank"
              >
                Health Check
              </v-btn>
            </div>
          </div>

          <v-divider class="my-6"></v-divider>

          <!-- User Info (Dev Mode) -->
          <div v-if="authStore.isAuthenticated" class="mt-4">
            <v-chip color="success" class="mr-2">
              <v-icon start>mdi-account-check</v-icon>
              Logged in as: {{ authStore.userName }}
            </v-chip>
            <v-chip
              v-for="role in authStore.currentRoles"
              :key="role"
              color="info"
              class="mr-2"
            >
              {{ role }}
            </v-chip>
          </div>

          <!-- Dev Mode Indicator -->
          <v-alert
            v-if="!isAuthEnabled"
            type="info"
            variant="tonal"
            class="mt-6 text-left"
          >
            <strong>Development Mode</strong>
            <br>
            Authentication is disabled. Use the role switcher in the navigation bar
            to test different user roles.
          </v-alert>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { isAuthEnabled as checkAuthEnabled } from '@/services/auth/authService'

const authStore = useAuthStore()
const isAuthEnabled = computed(() => checkAuthEnabled())
</script>

<style scoped lang="scss">
.v-card {
  border-radius: 12px;
}

.gap-3 {
  gap: 12px;
}
</style>
