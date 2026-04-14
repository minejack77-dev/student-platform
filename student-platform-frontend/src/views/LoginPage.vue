<script setup>
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

// Логин пароль с формы
const form = reactive({
  username: "",
  password: "",
});

const isSubmitting = ref(false);
const errorMessage = ref("");

// Вычисляет маршрут откуда пришел пользователь
const nextRoute = computed(() => {
  const redirect = route.query.redirect;
  if (typeof redirect === "string" && redirect.startsWith("/")) {
    return redirect;
  }
  return null;
});

const submit = async () => {
  errorMessage.value = "";
  if (!form.username.trim() || !form.password) {
    errorMessage.value = "Enter username and password.";
    return;
  }

  isSubmitting.value = true;
  try {
    const user = await authStore.login({
      username: form.username.trim(),
      password: form.password,
    });

    if (nextRoute.value) {
      await router.push(nextRoute.value);
      return;
    }

    // Редирект в зависимости от роли
    await router.push(user.role === "student" ? "/student" : "/");
  } catch (error) {
    errorMessage.value =
      error?.response?.data?.detail ||
      "Could not sign in. Check your username and password.";
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<template>
  <section class="login-shell">
    <div class="login-grid">
      <div class="surface-card login-aside">
        <span class="pill">Authorization</span>
        <h1 class="login-title">Sign in to Student Platform</h1>
        <p class="login-copy">
          Teachers manage groups and subjects. Students open assigned tasks and start attempts.
        </p>

        <div class="login-badges">
          <div class="login-badge">
            <strong>Teacher</strong>
            <span>Create subjects, topics, and group assignments.</span>
          </div>
          <div class="login-badge">
            <strong>Student</strong>
            <span>See your tasks and continue learning from one place.</span>
          </div>
        </div>
      </div>

      <div class="surface-card login-card">
        <div class="login-card-head">
          <h2>Welcome back</h2>
          <p>Use the same username and password as in Django admin or the seeded users.</p>
        </div>

        <form class="login-form" @submit.prevent="submit">
          <label class="field-wrap">
            <span>Username</span>
            <input
              v-model="form.username"
              class="form-control"
              type="text"
              autocomplete="username"
              placeholder="teacher_1"
            />
          </label>

          <label class="field-wrap">
            <span>Password</span>
            <input
              v-model="form.password"
              class="form-control"
              type="password"
              autocomplete="current-password"
              placeholder="Your password"
            />
          </label>

          <div v-if="errorMessage" class="alert alert-danger mb-0">{{ errorMessage }}</div>

          <button class="btn btn-primary login-btn" :disabled="isSubmitting" type="submit">
            {{ isSubmitting ? "Signing in..." : "Sign in" }}
          </button>
        </form>
      </div>
    </div>
  </section>
</template>

<style scoped src="./LoginPage.css"></style>
