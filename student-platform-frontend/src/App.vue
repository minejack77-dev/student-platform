<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

import { localeOptions, setAppLocale } from "@/i18n";
import { useAuthStore } from "@/stores/auth";
import AppSidebar from "@/components/AppSidebar.vue";
import { useWorkspaceNavigation } from "@/composables/useWorkspaceNavigation";

const router = useRouter();
const { t, locale } = useI18n();
const authStore = useAuthStore();
const { isAuthenticated, role, user } = storeToRefs(authStore);
const { items: navigationItems, activeKey } = useWorkspaceNavigation(role);
const logoutError = ref("");
const route = useRoute();
const accountOpen = ref(false);
const accountMenu = ref(null);
const accountButton = ref(null);
function closeAccount(event) {
  if (event.type === 'keydown' && event.key === 'Escape' && accountOpen.value) {
    accountOpen.value = false;
    accountButton.value?.focus();
  } else if (event.type === 'pointerdown' && !accountMenu.value?.contains(event.target)) {
    accountOpen.value = false;
  }
}
watch(() => route.fullPath, () => { accountOpen.value = false; });
onMounted(() => { document.addEventListener('pointerdown', closeAccount); document.addEventListener('keydown', closeAccount); });
onBeforeUnmount(() => { document.removeEventListener('pointerdown', closeAccount); document.removeEventListener('keydown', closeAccount); });

const roleLabel = computed(() => {
  if (role.value === "student") {
    return t("app.role.student");
  }
  if (role.value === "teacher") {
    return t("app.role.teacher");
  }
  return t("app.role.guest");
});

const languageOptions = computed(() =>
  localeOptions.map((value) => ({
    value,
    label: value === "ru" ? t("language.russian") : t("language.english"),
  })),
);

const handleLanguageChange = (event) => {
  setAppLocale(event.target.value);
};

const handleLogout = async () => {
  logoutError.value = "";
  try {
    const loggedOut = await authStore.logout();
    if (loggedOut) {
      await router.push({ name: "login" });
    }
  } catch (error) {
    logoutError.value =
      error?.response?.data?.detail ||
      t("app.errors.signOut");
  }
};
</script>

<template>
  <div class="app-shell" :class="{ 'has-sidebar': isAuthenticated }">
    <a class="skip-link" href="#workspace-main">{{ t('workstation.skip') }}</a>
    <AppSidebar v-if="isAuthenticated" :items="navigationItems" :active-key="activeKey" :role-label="roleLabel" />
    <div class="workspace-body">
    <header class="topbar">
      <div class="topbar-inner">
        <router-link v-if="!isAuthenticated" class="brand-link" to="/">
          <div class="brand-glyph">УП</div>
          <div>
            <div class="brand-title">{{ t("app.brandTitle") }}</div>
            <div class="brand-subtitle">{{ t("app.brandSubtitle") }}</div>
          </div>
        </router-link>

        <span v-else class="workspace-label">{{ t('app.brandTitle') }}<span>{{ roleLabel }}</span></span>
        <div ref="accountMenu" class="account-menu">
          <button v-if="isAuthenticated" ref="accountButton" class="account-trigger" type="button" :aria-label="t('workstation.account', { name: user?.username })" :aria-expanded="accountOpen" aria-controls="account-controls" @click="accountOpen = !accountOpen">
            <span class="account-avatar" aria-hidden="true">{{ user?.username?.slice(0, 1).toUpperCase() }}</span>
            <span class="account-name">{{ user?.username }}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m7 10 5 5 5-5" /></svg>
          </button>
        <Transition name="reveal">
        <div v-if="!isAuthenticated || accountOpen" id="account-controls" class="nav-wrap" :class="{ 'account-panel': isAuthenticated }" @focusout="event => { if (event.relatedTarget && !accountMenu?.contains(event.relatedTarget)) accountOpen = false; }">
          <span v-if="isAuthenticated" class="nav-user">{{ user?.username }} · {{ roleLabel }}</span>
          <label class="visually-hidden" for="app-language-select">{{ t("language.label") }}</label>
          <select
            id="app-language-select"
            :value="locale"
            class="form-select form-select-sm"
            @change="handleLanguageChange"
          >
            <option
              v-for="option in languageOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <button v-if="isAuthenticated" class="btn btn-outline-secondary btn-sm" type="button" @click="handleLogout">{{ t("app.nav.signOut") }}</button>
        </div>
        </Transition>
        </div>
      </div>
    </header>

    <main id="workspace-main" class="app-main" tabindex="-1">
      <div class="app-container">
        <div v-if="logoutError" class="alert alert-danger" role="alert">{{ logoutError }}</div>
        <router-view v-slot="{ Component, route: activeRoute }">
          <KeepAlive v-if="['group-overview', 'group-details'].includes(activeRoute.name)" :key="String(activeRoute.params.id)" :max="2">
            <component :is="Component" :key="activeRoute.path" />
          </KeepAlive>
          <component v-else :is="Component" :key="['teacher-home', 'student-home'].includes(activeRoute.name) ? activeRoute.path : activeRoute.fullPath" />
        </router-view>
      </div>
    </main>
    </div>
  </div>
</template>

<style scoped src="./App.css"></style>
