import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { de } from 'vuetify/locale'

const appTheme = {
  dark: false,
  colors: {
    primary: '{{BRAND_COLOR}}',        // Main accent color
    secondary: '#3c4649',               // Navigation bar color
    accent: '{{BRAND_COLOR}}',          // Same as primary for consistency
    background: '#f6f6f6',              // Main background
    surface: '#d1d1d3',                 // Cards/tiles background
    error: '#f44336',                   // Error
    info: '#2196f3',                    // Information
    success: '#4caf50',                 // Success
    warning: '#ff9800',                 // Warning
    'on-primary': '#ffffff',            // Text on primary color
    'on-secondary': '#ffffff',          // Text on secondary color
    'on-background': '#000000',         // Text on background
    'on-surface': '#000000',            // Text on cards
    'nav-text': '#9e9e9e',              // Navigation text
    'text-secondary': '#666666',        // Secondary text
  }
}

export default createVuetify({
  components,
  directives,
  locale: {
    locale: 'de',
    messages: { de },
  },
  icons: {
    defaultSet: 'mdi',
  },
  theme: {
    defaultTheme: 'appTheme',
    themes: {
      appTheme,
    }
  }
})
