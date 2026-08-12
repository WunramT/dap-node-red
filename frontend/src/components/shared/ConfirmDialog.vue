<template>
  <v-dialog v-model="dialogStore.showDialog" max-width="500px" persistent>
    <v-card>
      <v-card-title class="text-h5">
        {{ dialogStore.dialog.title }}
      </v-card-title>

      <v-card-text>
        {{ dialogStore.dialog.message }}
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          color="grey-darken-1"
          variant="text"
          @click="onCancel"
        >
          {{ dialogStore.dialog.cancelText }}
        </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          @click="onConfirm"
          :loading="loading"
        >
          {{ dialogStore.dialog.confirmText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUiStore } from '@/stores/uiStore'

const dialogStore = useUiStore()
const loading = ref(false)

async function onConfirm() {
  loading.value = true
  try {
    await dialogStore.confirmDialog()
  } finally {
    loading.value = false
  }
}

function onCancel() {
  dialogStore.cancelDialog()
}
</script>
