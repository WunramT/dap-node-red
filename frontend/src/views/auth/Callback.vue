<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="6" lg="4">
        <v-card class="elevation-12">
          <v-card-title class="text-h5 text-center py-6">
            <v-icon size="48" class="mr-2" color="primary">mdi-shield-check</v-icon>
            Authentication
          </v-card-title>

          <v-card-text class="text-center py-8">
            <template v-if="isLoading">
              <v-progress-circular
                indeterminate
                color="primary"
                size="64"
                class="mb-4"
              ></v-progress-circular>
              <p class="text-h6">Processing authentication...</p>
              <p class="text-body-2 text-medium-emphasis mt-2">
                Please wait while we complete your login.
              </p>
            </template>

            <template v-else-if="error">
              <v-icon size="64" color="error" class="mb-4">mdi-alert-circle</v-icon>
              <p class="text-h6 text-error mb-2">Authentication failed</p>
              <p class="text-body-2 text-medium-emphasis">{{ error }}</p>
              <v-btn
                color="primary"
                variant="flat"
                class="mt-4"
                @click="redirectToHome"
              >
                Go to Home
              </v-btn>
            </template>

            <template v-else-if="success">
              <v-icon size="64" color="success" class="mb-4">mdi-check-circle</v-icon>
              <p class="text-h6 text-success mb-2">Authentication successful!</p>
              <p class="text-body-2 text-medium-emphasis">
                Redirecting to application...
              </p>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { handleRedirectCallback } from '@/services/auth/authService'

const router = useRouter()
const authStore = useAuthStore()

const isLoading = ref(true)
const success = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    // Handle the redirect callback from Azure AD
    const response = await handleRedirectCallback()

    if (response) {
      // Authentication successful
      success.value = true

      // Update auth store
      await authStore.initialize()

      // Redirect to home page after a short delay
      setTimeout(() => {
        router.push('/')
      }, 1500)
    } else {
      // No response, but no error - might be coming from somewhere else
      // Try to initialize anyway
      await authStore.initialize()

      if (authStore.isAuthenticated) {
        success.value = true
        setTimeout(() => {
          router.push('/')
        }, 1000)
      } else {
        error.value = 'No authentication response received.'
        isLoading.value = false
      }
    }
  } catch (err: unknown) {
    console.error('Authentication callback error:', err)
    const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred.'
    error.value = errorMessage
    isLoading.value = false
  }
})

function redirectToHome() {
  router.push('/')
}
</script>

<style scoped>
.fill-height {
  min-height: 100vh;
}
</style>
