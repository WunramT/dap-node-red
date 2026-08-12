<template>
  <v-overlay
    v-model="uiStore.loading"
    :persistent="true"
    class="align-center justify-center"
  >
    <div class="text-center">
      <v-progress-circular
        :size="70"
        :width="7"
        color="primary"
        indeterminate
      ></v-progress-circular>
      <div v-if="uiStore.loadingMessage" class="mt-4 text-h6 text-white">
        {{ uiStore.loadingMessage }}
      </div>
    </div>
  </v-overlay>
</template>

<script setup lang="ts">
import { useUiStore } from '@/stores/uiStore'

const uiStore = useUiStore()
</script>
