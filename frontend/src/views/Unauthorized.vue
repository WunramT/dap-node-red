<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="6">
        <v-card elevation="8" class="text-center">
          <v-card-text class="pa-8">
            <v-icon
              icon="mdi-shield-alert"
              size="80"
              color="error"
              class="mb-4"
            ></v-icon>

            <h1 class="text-h4 mb-4">Access Denied</h1>

            <p class="text-body-1 text-medium-emphasis mb-6">
              You do not have the required permissions to access this page.
            </p>

            <v-alert type="info" variant="tonal" class="mb-6 text-grey-darken-4">
              <div class="text-left">
                <strong>Your roles:</strong>
                <v-chip
                  v-for="role in authStore.currentRoles"
                  :key="role"
                  size="small"
                  class="ml-2"
                >
                  {{ role }}
                </v-chip>
                <span v-if="!authStore.currentRoles?.length" class="ml-2">
                  No roles assigned
                </span>
              </div>
            </v-alert>

            <div class="d-flex gap-2 justify-center">
              <v-btn
                color="primary"
                prepend-icon="mdi-arrow-left"
                @click="goBack"
              >
                Back
              </v-btn>

              <v-btn
                color="secondary"
                prepend-icon="mdi-home"
                @click="goHome"
              >
                Go to Home
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function goBack() {
  router.back()
}

function goHome() {
  router.push('/')
}
</script>
