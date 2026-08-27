<script setup>
import { computed, ref } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

import { localeOptions, setAppLocale } from "@/i18n";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const { t, locale } = useI18n();
const authStore = useAuthStore();
const { isAuthenticated, role, user } = storeToRefs(authStore);
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
  <div class="app-shell">
    <header class="topbar">
      <div class="container app-container topbar-inner">
        <router-link class="brand-link" to="/">
          <div class="brand-glyph">УП</div>
          <div>
            <div class="brand-title">{{ t("app.brandTitle") }}</div>
            <div class="brand-subtitle">{{ t("app.brandSubtitle") }}</div>
          </div>
        </router-link>

        <nav class="nav-wrap">
          <template v-if="isAuthenticated">
            <router-link
              v-if="role === 'teacher'"
              class="nav-item-link"
              :to="{ name: 'teacher-home' }"
            >
              {{ t("app.nav.teacher") }}
            </router-link>
            <router-link
              v-if="role === 'student'"
              class="nav-item-link"
              :to="{ name: 'student-home' }"
            >
              {{ t("app.nav.tasks") }}
            </router-link>
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
        </nav>
      </div>
    </header>

    <main class="app-main">
      <div class="container app-container">
        <div v-if="logoutError" class="alert alert-danger">{{ logoutError }}</div>
        <router-view v-slot="{ Component, route: activeRoute }">
          <transition name="route-fade" mode="out-in">
            <component :is="Component" :key="activeRoute.fullPath" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped src="./App.css"></style>
