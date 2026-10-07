<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
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

        <span v-else class="workspace-label">{{ t('workstation.workspace') }}</span>
        <div class="nav-wrap">
          <template v-if="isAuthenticated">
            <span class="nav-user">{{ user?.username }} · {{ roleLabel }}</span>
            <button class="btn btn-outline-primary btn-sm" type="button" @click="handleLogout">
              {{ t("app.nav.signOut") }}
            </button>
          </template>
          <label class="visually-hidden" for="app-language-select">{{ t("language.label") }}</label>
          <select
            id="app-language-select"
            :value="locale"
            class="form-select form-select-sm"
            style="width: auto;"
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
