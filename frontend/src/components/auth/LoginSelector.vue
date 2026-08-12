<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="6" lg="4">
        <v-card elevation="8">
          <v-card-title class="text-h5 text-center">
            <v-icon start size="large" color="primary">mdi-login</v-icon>
            Anmeldung
          </v-card-title>

          <v-card-text class="px-6 py-8">
            <p class="text-center mb-6">Bitte wählen Sie eine Anmeldemethode:</p>

            <v-row>
              <!-- Azure AD / Entra ID -->
              <v-col v-if="config?.providers.azure" cols="12">
                <v-btn
                  block
                  color="primary"
                  size="large"
                  prepend-icon="mdi-microsoft"
                  :loading="loading"
                  @click="loginWithAzure"
                >
                  Mit Microsoft anmelden
                </v-btn>
              </v-col>

              <!-- Local DB – E-Mail + Passwort -->
              <v-col v-if="config?.providers.local_db" cols="12">
                <v-btn
                  block
                  color="secondary"
                  size="large"
                  prepend-icon="mdi-email"
                  @click="showLocalLoginForm = !showLocalLoginForm"
                >
                  Mit E-Mail anmelden
                </v-btn>

                <v-expand-transition>
                  <div v-if="showLocalLoginForm" class="mt-4">
                    <v-form @submit.prevent="loginWithLocalDb">
                      <v-text-field
                        v-model="localEmail"
                        label="E-Mail"
                        type="email"
                        variant="outlined"
                        density="comfortable"
                        :disabled="loading"
                        class="mb-2"
                      />
                      <v-text-field
                        v-model="localPassword"
                        label="Passwort"
                        type="password"
                        variant="outlined"
                        density="comfortable"
                        :disabled="loading"
                        @keyup.enter="loginWithLocalDb"
                      />
                      <v-btn
                        block
                        color="secondary"
                        :loading="loading"
                        :disabled="!localEmail || !localPassword"
                        @click="loginWithLocalDb"
                        class="mt-2"
                      >
                        Anmelden
                      </v-btn>
                    </v-form>
                  </div>
                </v-expand-transition>
              </v-col>

              <!-- Master Password -->
              <v-col v-if="config?.providers.master_pw" cols="12">
                <v-btn
                  block
                  color="deep-purple"
                  size="large"
                  prepend-icon="mdi-shield-account"
                  @click="showMasterPwDialog = true"
                >
                  Mit Master-Passwort anmelden
                </v-btn>
              </v-col>
            </v-row>

            <v-alert
              v-if="error"
              type="error"
              class="mt-4"
              closable
              @click:close="error = ''"
            >
              {{ error }}
            </v-alert>
          </v-card-text>

          <!-- Close button (when used as dialog inside TopBar) -->
          <v-card-actions v-if="asDialog">
            <v-spacer />
            <v-btn text @click="$emit('close')">Schließen</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Master Password Dialog -->
    <v-dialog v-model="showMasterPwDialog" max-width="400" persistent>
      <v-card>
        <v-card-title>Master-Passwort Anmeldung</v-card-title>

        <v-card-text>
          <v-form @submit.prevent="loginWithMasterPw">
            <v-text-field
              v-model="masterPassword"
              label="Master-Passwort"
              type="password"
              variant="outlined"
              density="comfortable"
              :disabled="loading"
              autofocus
              @keyup.enter="loginWithMasterPw"
            />

            <v-alert
              v-if="masterPwError"
              type="error"
              class="mt-2"
              closable
              @click:close="masterPwError = ''"
            >
              {{ masterPwError }}
            </v-alert>
          </v-form>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn text @click="closeMasterPwDialog" :disabled="loading">
            Abbrechen
          </v-btn>
          <v-btn
            color="primary"
            :loading="loading"
            :disabled="!masterPassword"
            @click="loginWithMasterPw"
          >
            Anmelden
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  /** When true a "Schließen" button is shown (used as embedded dialog) */
  asDialog?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const router = useRouter()
const authStore = useAuthStore()

const config = computed(() => authStore.authConfig)
const loading = ref(false)
const error = ref('')

// Local DB form
const showLocalLoginForm = ref(false)
const localEmail = ref('')
const localPassword = ref('')

// Master password dialog
const showMasterPwDialog = ref(false)
const masterPassword = ref('')
const masterPwError = ref('')

// ── Azure AD ─────────────────────────────────────────────────────────────────
async function loginWithAzure() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(false)  // redirect flow
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Azure-Anmeldung fehlgeschlagen'
    loading.value = false
  }
}

// ── Local DB ─────────────────────────────────────────────────────────────────
async function loginWithLocalDb() {
  if (!localEmail.value || !localPassword.value) return

  loading.value = true
  error.value = ''
  try {
    const success = await authStore.login(localEmail.value, localPassword.value)
    if (success) {
      emit('close')
      router.push('/')
    } else {
      error.value = 'Falsche E-Mail-Adresse oder Passwort'
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen'
  } finally {
    loading.value = false
  }
}

// ── Master Password ───────────────────────────────────────────────────────────
async function loginWithMasterPw() {
  if (!masterPassword.value) {
    masterPwError.value = 'Bitte geben Sie ein Passwort ein'
    return
  }

  loading.value = true
  masterPwError.value = ''
  try {
    const success = await authStore.loginWithMasterPassword(masterPassword.value)
    if (success) {
      showMasterPwDialog.value = false
      emit('close')
      router.push('/')
    } else {
      masterPwError.value = 'Falsches Passwort'
    }
  } catch (err) {
    masterPwError.value = err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen'
  } finally {
    loading.value = false
  }
}

function closeMasterPwDialog() {
  showMasterPwDialog.value = false
  masterPassword.value = ''
  masterPwError.value = ''
}
</script>

<style scoped>
.fill-height {
  min-height: calc(100vh - 64px);
}
</style>
