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
.workspace-sidebar { position: sticky; top: 0; height: 100dvh; display: flex; flex-direction: column; background: var(--nav-bg); color: var(--ink); padding: 28px 16px 24px; border-right: 1px solid var(--line); }
.sidebar-brand { display: flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; font-weight: 650; font-size: 14px; padding: 0 8px 38px; }
.sidebar-brand small { display: block; font-weight: 400; font-size: 12px; color: var(--ink-soft); margin-top: 3px; }
.brand-mark { display: grid; place-items: center; width: 36px; height: 36px; flex: 0 0 36px; background: var(--brand-blue); color: #fff; border-radius: 10px; font-size: 13px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 5px; }
.sidebar-link { display: flex; align-items: center; gap: 11px; padding: 12px; border-radius: 8px; color: var(--nav-text); text-decoration: none; font-size: 14px; line-height: 1.4; min-height: 46px; }
.sidebar-link svg { width: 19px; height: 19px; flex-shrink: 0; }
.sidebar-link:hover { background: var(--nav-hover); color: var(--ink); }
.sidebar-link.is-active { color: var(--brand-blue-strong); background: var(--nav-active); font-weight: 600; }
.sidebar-brand:focus-visible, .sidebar-link:focus-visible { outline-color: var(--brand-blue); outline-offset: 2px; }
.sidebar-foot { margin-top: auto; padding: 16px 12px 0; font-size: 12px; color: var(--ink-soft); }
@media (max-width: 800px) {
  .workspace-sidebar { position: fixed; inset: auto 0 0; z-index: 100; height: auto; padding: 6px 6px max(6px, env(safe-area-inset-bottom)); background: var(--surface); border: 0; border-top: 1px solid var(--line); }
  .sidebar-brand { display: none; }
  .sidebar-nav { flex-direction: row; gap: 3px; }
  .sidebar-link { flex: 1 1 0; min-width: 0; flex-direction: column; justify-content: center; padding: 8px 2px; gap: 5px; font-size: 11px; min-height: 56px; }
  .sidebar-link span { overflow-wrap: anywhere; text-align: center; }
  .sidebar-link svg { width: 20px; height: 20px; }
  .sidebar-foot { display: none; }
}
</style>
