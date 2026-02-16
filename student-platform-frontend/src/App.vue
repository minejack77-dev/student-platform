<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const pageLabel = computed(() => {
  if (route.name === "topic-detail") {
    return "Topic workspace";
  }
  if (route.name === "subject-detail") {
    return "Subject workspace";
  }
  if (route.name === "group-detail") {
    return "Group workspace";
  }
  return "Teaching dashboard";
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="container app-container topbar-inner">
        <router-link class="brand-link" to="/">
          <div class="brand-glyph">SP</div>
          <div>
            <div class="brand-title">Student Platform</div>
            <div class="brand-subtitle">Teacher control center</div>
          </div>
        </router-link>

        <nav class="nav-wrap">
          <router-link class="nav-item-link" to="/">Dashboard</router-link>
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

<style scoped>
.app-shell {
  position: relative;
}

.app-shell::before,
.app-shell::after {
  border-radius: 999px;
  content: "";
  filter: blur(42px);
  pointer-events: none;
  position: fixed;
  z-index: 0;
}

.app-shell::before {
  background: rgba(255, 179, 71, 0.16);
  height: 280px;
  left: -110px;
  top: 80px;
  width: 280px;
}

.app-shell::after {
  background: rgba(31, 95, 216, 0.16);
  height: 300px;
  right: -120px;
  top: 240px;
  width: 300px;
}

.topbar {
  background: linear-gradient(
    140deg,
    rgba(255, 255, 255, 0.86) 0%,
    rgba(255, 255, 255, 0.67) 100%
  );
  border-bottom: 1px solid rgba(17, 35, 59, 0.12);
  backdrop-filter: blur(10px);
  left: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.app-container {
  position: relative;
  z-index: 1;
}

.topbar-inner {
  align-items: center;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  min-height: 72px;
}

.brand-link {
  align-items: center;
  color: inherit;
  display: flex;
  gap: 12px;
  text-decoration: none;
}

.brand-glyph {
  align-items: center;
  background: linear-gradient(140deg, var(--brand-blue) 0%, var(--brand-mint) 100%);
  border-radius: 14px;
  color: #fff;
  display: inline-flex;
  font-family: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  font-size: 14px;
  font-weight: 700;
  height: 40px;
  justify-content: center;
  letter-spacing: 0.04em;
  width: 40px;
}

.brand-title {
  color: var(--ink);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
}

.brand-subtitle {
  color: var(--ink-soft);
  font-size: 12px;
}

.nav-wrap {
  align-items: center;
  display: flex;
  gap: 12px;
}

.nav-item-link {
  color: var(--ink);
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
}

.nav-item-link:hover {
  color: var(--brand-blue-strong);
}

.app-main {
  padding-bottom: 38px;
  padding-top: 26px;
}

@media (max-width: 768px) {
  .topbar-inner {
    flex-direction: column;
    gap: 10px;
    padding-bottom: 10px;
    padding-top: 10px;
  }

  .brand-title {
    font-size: 16px;
  }

  .app-main {
    padding-top: 20px;
  }
}
</style>
