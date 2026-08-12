/**
 * UI Store - Manages global UI state
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Snackbar {
  show: boolean
  message: string
  color: 'success' | 'error' | 'warning' | 'info'
  timeout: number
}

export interface Dialog {
  show: boolean
  title: string
  message: string
  confirmText: string
  cancelText: string
  onConfirm?: () => void | Promise<void>
  onCancel?: () => void
}

export interface ConfirmOptions {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  confirmColor?: string
}

export const useUiStore = defineStore('ui', () => {
  // State
  const loading = ref<boolean>(false)
  const loadingMessage = ref<string>('')

  const snackbar = ref<Snackbar>({
    show: false,
    message: '',
    color: 'info',
    timeout: 3000
  })

  const dialog = ref<Dialog>({
    show: false,
    title: '',
    message: '',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    onConfirm: undefined,
    onCancel: undefined
  })

  const sidebarOpen = ref<boolean>(true)
  const darkMode = ref<boolean>(false)

  // Getters
  const isLoading = computed(() => loading.value)
  const showSnackbar = computed(() => snackbar.value.show)
  const showDialog = computed(() => dialog.value.show)

  // Actions - Loading
  function setLoading(value: boolean, message: string = '') {
    loading.value = value
    loadingMessage.value = message
  }

  function startLoading(message: string = 'Loading...') {
    loading.value = true
    loadingMessage.value = message
  }

  function stopLoading() {
    loading.value = false
    loadingMessage.value = ''
  }

  // Actions - Snackbar
  function showSnackbarMessage(message: string, color: Snackbar['color'] = 'info', timeout: number = 3000) {
    snackbar.value = {
      show: true,
      message,
      color,
      timeout
    }
  }

  function showSuccess(message: string, timeout: number = 3000) {
    showSnackbarMessage(message, 'success', timeout)
  }

  function showError(message: string, timeout: number = 5000) {
    showSnackbarMessage(message, 'error', timeout)
  }

  function showWarning(message: string, timeout: number = 4000) {
    showSnackbarMessage(message, 'warning', timeout)
  }

  function showInfo(message: string, timeout: number = 3000) {
    showSnackbarMessage(message, 'info', timeout)
  }

  function hideSnackbar() {
    snackbar.value.show = false
  }

  // Actions - Dialog
  function showConfirmDialog(
    title: string,
    message: string,
    onConfirm?: () => void | Promise<void>,
    onCancel?: () => void,
    confirmText: string = 'Confirm',
    cancelText: string = 'Cancel'
  ) {
    dialog.value = {
      show: true,
      title,
      message,
      confirmText,
      cancelText,
      onConfirm,
      onCancel
    }
  }

  function hideDialog() {
    dialog.value.show = false
  }

  async function confirmDialog() {
    if (dialog.value.onConfirm) {
      await dialog.value.onConfirm()
    }
    hideDialog()
  }

  function cancelDialog() {
    if (dialog.value.onCancel) {
      dialog.value.onCancel()
    }
    hideDialog()
  }

  function showConfirm(options: ConfirmOptions): Promise<boolean> {
    return new Promise((resolve) => {
      dialog.value = {
        show: true,
        title: options.title,
        message: options.message,
        confirmText: options.confirmText || 'Confirm',
        cancelText: options.cancelText || 'Cancel',
        onConfirm: () => resolve(true),
        onCancel: () => resolve(false)
      }
    })
  }

  // Actions - UI
  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function setSidebar(value: boolean) {
    sidebarOpen.value = value
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
  }

  function setDarkMode(value: boolean) {
    darkMode.value = value
  }

  return {
    // State
    loading,
    loadingMessage,
    snackbar,
    dialog,
    sidebarOpen,
    darkMode,
    // Getters
    isLoading,
    showSnackbar,
    showDialog,
    // Actions
    setLoading,
    startLoading,
    stopLoading,
    showSnackbarMessage,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    hideSnackbar,
    showConfirmDialog,
    showConfirm,
    hideDialog,
    confirmDialog,
    cancelDialog,
    toggleSidebar,
    setSidebar,
    toggleDarkMode,
    setDarkMode
  }
})
