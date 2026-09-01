<script setup>
import { computed, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const { t } = useI18n();
const authStore = useAuthStore();

const form = reactive({
  username: "",
  password: "",
});

const isSubmitting = ref(false);
const errorMessage = ref("");

const nextRoute = computed(() => {
  const redirect = route.query.redirect;
  if (typeof redirect === "string" && redirect.startsWith("/")) {
    return redirect;
  }
  return null;
});

const defaultRouteByRole = (role) => (role === "student" ? "/student" : "/");

const redirectAuthenticatedUser = async () => {
  if (!authStore.isAuthenticated) {
    return;
  }
  errorMessage.value = "";
  await router.replace(nextRoute.value || defaultRouteByRole(authStore.role));
};

watch(
  () => authStore.isAuthenticated,
  () => {
    redirectAuthenticatedUser();
  },
  { immediate: true },
);

const submit = async () => {
  errorMessage.value = "";
  if (authStore.isAuthenticated) {
    await redirectAuthenticatedUser();
    return;
  }
  if (!form.username.trim() || !form.password) {
    errorMessage.value = t("login.errors.missingCredentials");
    return;
  }

  isSubmitting.value = true;
  try {
    const user = await authStore.login({
      username: form.username.trim(),
      password: form.password,
    });

    if (nextRoute.value) {
      await router.replace(nextRoute.value);
      return;
    }

    await router.replace(defaultRouteByRole(user.role));
  } catch (error) {
    if (authStore.isAuthenticated) {
      await redirectAuthenticatedUser();
      return;
    }
    errorMessage.value =
      error?.response?.data?.detail ||
      t("login.errors.signIn");
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<template>
  <section class="login-shell">
    <div class="login-grid">
      <div class="surface-card login-aside">
        <span class="pill">{{ t("login.badge") }}</span>
        <h1 class="login-title">{{ t("login.title") }}</h1>
        <p class="login-copy">{{ t("login.copy") }}</p>
      </div>

      <div class="surface-card login-card">
        <div class="login-card-head">
          <h2>{{ t("login.welcome") }}</h2>
          <p>{{ t("login.helper") }}</p>
        </div>

        <form class="login-form" @submit.prevent="submit">
          <label class="field-wrap">
            <span>{{ t("login.username") }}</span>
            <input
              v-model="form.username"
              class="form-control"
              type="text"
              autocomplete="username"
              :placeholder="t('login.usernamePlaceholder')"
            />
          </label>

          <label class="field-wrap">
            <span>{{ t("login.password") }}</span>
            <input
              v-model="form.password"
              class="form-control"
              type="password"
              autocomplete="current-password"
              :placeholder="t('login.passwordPlaceholder')"
            />
          </label>

          <div v-if="errorMessage" class="alert alert-danger mb-0">{{ errorMessage }}</div>

          <button class="btn btn-primary login-btn" :disabled="isSubmitting" type="submit">
            {{ isSubmitting ? t("login.signingIn") : t("login.signIn") }}
          </button>
        </form>
      </div>
    </div>
  </section>
</template>

<style scoped src="./LoginPage.css"></style>
