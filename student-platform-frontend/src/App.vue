<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const { isAuthenticated, role, user } = storeToRefs(authStore);

const pageLabel = computed(() => {
  if (route.name === "login") {
    return "Access portal";
  }
  if (route.name === "topic-detail") {
    return "Topic workspace";
  }
  if (route.name === "subject-detail") {
    return "Subject workspace";
  }
  if (route.name === "group-detail") {
    return "Group workspace";
  }
  if (route.name === "student-home") {
    return "Student workspace";
  }
  if (route.name === "attempt-detail") {
    return "Attempt session";
  }
  return "Teaching dashboard";
});

const roleLabel = computed(() => {
  if (role.value === "student") {
    return "Student";
  }
  if (role.value === "teacher") {
    return "Teacher";
  }
  return "Guest";
});

const handleLogout = async () => {
  await authStore.logout();
  await router.push({ name: "login" });
};
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="container app-container topbar-inner">
        <router-link class="brand-link" to="/">
          <div class="brand-glyph">SP</div>
          <div>
            <div class="brand-title">Student Platform</div>
            <div class="brand-subtitle">Learning workspace</div>
          </div>
        </router-link>

        <nav class="nav-wrap">
          <!-- <router-link class="nav-item-link" :to="{ name: 'teacher-home' }">Teacher</router-link> -->
          <!-- <router-link class="nav-item-link" :to="{ name: 'student-home' }">Tasks</router-link> -->
          <template v-if="isAuthenticated">
            <router-link
              v-if="role === 'teacher'"
              class="nav-item-link"
              :to="{ name: 'teacher-home' }"
            >
              Teacher
            </router-link>
            <router-link
              v-if="role === 'student'"
              class="nav-item-link"
              :to="{ name: 'student-home' }"
            >
              Tasks
            </router-link>
            <span class="nav-user">{{ user?.username }} · {{ roleLabel }}</span>
            <button class="btn btn-outline-primary btn-sm" type="button" @click="handleLogout">
              Sign out
            </button>
          </template>
          <span class="pill">{{ pageLabel }}</span>
        </nav>
      </div>
    </header>

    <main class="app-main">
      <div class="container app-container">
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
