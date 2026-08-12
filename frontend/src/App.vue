<template>
  <v-app>
    <!-- Top Navigation Bar -->
    <TopBar />

    <!-- Main Content Area -->
    <v-main class="main-content">
      <router-view />
    </v-main>

    <!-- Global UI Components -->
    <LoadingSpinner />
    <ConfirmDialog />

    <!-- Global Snackbar -->
    <v-snackbar
      v-model="uiStore.snackbar.show"
      :color="uiStore.snackbar.color"
      :timeout="uiStore.snackbar.timeout"
      location="top"
    >
      {{ uiStore.snackbar.message }}
    </v-snackbar>
  </v-app>
</template>

<script setup lang="ts">
import TopBar from '@/components/TopBar.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue'
import { useUiStore } from '@/stores/uiStore'

const uiStore = useUiStore()
</script>

<style lang="scss">
@use '@/styles/variables' as vars;

// Global App Styles
.v-application {
  background-color: vars.$color-bg !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

// Navigation Bar Styling
.v-app-bar {
  border-bottom: 1px solid rgba(vars.$color-nav-bg, 0.2) !important;
  box-shadow: vars.$shadow-sm !important;
}

// Main Content
.main-content {
  padding-top: 64px !important;
  background-color: vars.$color-bg !important;
  min-height: calc(100vh - 64px);
}

// Global Text Styles
body {
  color: vars.$color-text;
}

// Global Link Styles
a:not(.v-btn) {
  color: vars.$color-primary;
  text-decoration: none;
  transition: color 0.2s ease;

  &:hover {
    color: vars.$color-primary-hover;
    text-decoration: underline;
  }

  &:active {
    color: vars.$color-primary-active;
  }
}

// Focus Styles for Accessibility
*:focus-visible {
  outline: 2px solid vars.$color-primary;
  outline-offset: 2px;
}

// Button Focus Override
.v-btn:focus-visible {
  outline: 2px solid vars.$color-primary;
  outline-offset: 2px;
}

// Scrollbar Styling (Global)
::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: vars.$color-bg;
  border-radius: 5px;
}

::-webkit-scrollbar-thumb {
  background: vars.$color-border;
  border-radius: 5px;
  transition: background 0.2s ease;

  &:hover {
    background: vars.$color-border-dark;
  }

  &:active {
    background: vars.$color-nav-bg;
  }
}

// Firefox Scrollbar
* {
  scrollbar-width: thin;
  scrollbar-color: vars.$color-border vars.$color-bg;
}

// Selection/Highlight Styling
::selection {
  background-color: rgba(vars.$color-primary, 0.2);
  color: vars.$color-text;
}

::-moz-selection {
  background-color: rgba(vars.$color-primary, 0.2);
  color: vars.$color-text;
}

// Transitions for interactive elements
.v-btn,
.v-card,
.v-list-item,
.v-input {
  transition: all 0.2s ease;
}

// Loading/Spinner Adjustments
.v-progress-circular {
  color: vars.$color-primary !important;
}

.v-progress-linear {
  color: vars.$color-primary !important;
}

// Tooltip Styling
.v-tooltip {
  .v-overlay__content {
    background: vars.$color-nav-bg !important;
    color: vars.$color-text-white !important;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 4px;
  }
}

// Snackbar Styling
.v-snackbar {
  .v-snackbar__wrapper {
    background: vars.$color-nav-bg !important;
    color: vars.$color-text-white !important;
  }

  &.error {
    .v-snackbar__wrapper {
      background: vars.$color-error !important;
    }
  }

  &.success {
    .v-snackbar__wrapper {
      background: vars.$color-success !important;
    }
  }

  &.warning {
    .v-snackbar__wrapper {
      background: vars.$color-warning !important;
    }
  }

  &.info {
    .v-snackbar__wrapper {
      background: vars.$color-info !important;
    }
  }
}
</style>
