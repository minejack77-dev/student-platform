<script setup>
import { useI18n } from "vue-i18n";

defineProps({
  items: { type: Array, required: true },
  activeKey: { type: String, default: null },
  roleLabel: { type: String, required: true },
});
const { t } = useI18n();
const paths = {
  groups: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  materials: "M4 4h6a2 2 0 0 1 2 2v15a3 3 0 0 0-3-3H4V4ZM20 4h-6a2 2 0 0 0-2 2v15a3 3 0 0 1 3-3h5V4Z",
  results: "M4 20h16M7 16v-5M12 16V4M17 16V8",
  assignments: "M9 5H5v16h14V5h-4M9 3h6v4H9V3ZM8 12h8M8 16h5",
  schedule: "M4 5h16v16H4V5ZM4 10h16M8 3v4M16 3v4M8 14h2M14 14h2",
  notifications: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4",
};
</script>

<template>
  <aside class="workspace-sidebar">
    <router-link :to="items[0]?.to || '/'" class="sidebar-brand">
      <span class="brand-mark" aria-hidden="true">УП</span>
      <span>{{ t('app.brandTitle') }}<small>{{ roleLabel }}</small></span>
    </router-link>
    <nav class="sidebar-nav" :aria-label="t('workstation.navigation')">
      <router-link v-for="item in items" :key="item.key" :to="item.to"
        class="sidebar-link" :class="{ 'is-active': activeKey === item.key }"
        :aria-current="activeKey === item.key ? 'page' : undefined" aria-current-value="false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[item.key]" /></svg>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>
    <div class="sidebar-foot">{{ t('workstation.workspace') }}</div>
  </aside>
</template>

<style scoped>
.workspace-sidebar { position: sticky; top: 0; height: 100dvh; display: flex; flex-direction: column; background: var(--nav-bg); color: #e5edf7; padding: 28px 14px 20px; }
.sidebar-brand { display: flex; align-items: center; gap: 10px; color: #fff; text-decoration: none; font-weight: 650; font-size: 14px; padding: 0 8px 30px; }
.sidebar-brand small { display: block; font-weight: 400; font-size: 12px; color: #b5c3d5; margin-top: 3px; }
.brand-mark { display: grid; place-items: center; width: 36px; height: 36px; flex: 0 0 36px; border: 1px solid #617792; border-radius: 7px; font-size: 13px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 5px; }
.sidebar-link { display: flex; align-items: center; gap: 11px; padding: 12px; border-radius: 6px; color: #c8d3e2; text-decoration: none; font-size: 14px; line-height: 1.4; min-height: 44px; }
.sidebar-link svg { width: 19px; height: 19px; flex-shrink: 0; }
.sidebar-link:hover { background: #26394f; color: #fff; }
.sidebar-link.is-active { color: #fff; background: var(--nav-active); font-weight: 600; }
.sidebar-brand:focus-visible, .sidebar-link:focus-visible { outline-color: #aac3ff; outline-offset: 2px; }
.sidebar-foot { margin-top: auto; padding: 16px 12px 0; font-size: 12px; color: #b5c3d5; }
@media (max-width: 800px) {
  .workspace-sidebar { position: static; height: auto; padding: 14px 16px 8px; }
  .sidebar-brand { padding: 0 0 12px; }
  .sidebar-brand small { display: none; }
  .brand-mark { width: 30px; height: 30px; flex-basis: 30px; }
  .sidebar-nav { flex-direction: row; flex-wrap: wrap; gap: 3px; }
  .sidebar-link { padding: 10px; gap: 7px; }
  .sidebar-link svg { width: 16px; height: 16px; }
  .sidebar-foot { display: none; }
}
</style>
