<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
  id: { type: [String, Number], required: true },
  name: { type: String, default: '' },
  description: { type: String, default: '' },
  active: { type: String, required: true },
  subjectId: { type: [String, Number], default: '' },
});
const { t } = useI18n();
const tabs = computed(() => [
  { key: 'summary', label: t('workstation.group.summary'), name: 'group-overview', query: { tab: 'summary' } },
  { key: 'schedule', label: t('ux.schedule'), name: 'group-overview', query: {} },
  { key: 'results', label: t('ux.results'), name: 'group-overview', query: { tab: 'results' } },
  { key: 'members', label: t('workstation.group.members'), name: 'group-details', query: { tab: 'members' } },
  { key: 'settings', label: t('workstation.group.settings'), name: 'group-details', query: {} },
]);
</script>

<template>
  <nav class="page-breadcrumbs" :aria-label="t('workstation.group.breadcrumbs')">
    <router-link :to="{ name: 'teacher-home', query: { view: 'groups' } }">{{ t('common.groups') }}</router-link>
    <span>{{ name || t('common.untitledGroup') }}</span>
  </nav>
  <header class="workspace-heading">
    <div>
      <h1>{{ name || t('common.untitledGroup') }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <router-link v-if="active !== 'schedule'" class="btn btn-primary" :to="{ name: 'group-overview', params: { id }, hash: '#group-schedule' }">{{ t('workstation.group.assign') }}</router-link>
  </header>
  <nav class="page-tabs group-tabs" :aria-label="t('workstation.group.navigation')">
    <router-link v-for="tab in tabs" :key="tab.key" :to="{ name: tab.name, params: { id: props.id }, query: tab.query }"
      :aria-current="active === tab.key ? 'page' : undefined" aria-current-value="false">{{ tab.label }}</router-link>
    <router-link v-if="subjectId" :to="{ name: 'subject-detail', params: { id: subjectId }, query: { group: id } }">{{ t('ux.material') }}</router-link>
  </nav>
</template>

<style scoped>
.workspace-heading h1, .workspace-heading p { overflow-wrap: anywhere; }
.workspace-heading > div { min-width: 0; }
.group-tabs { gap: 6px 24px; }
</style>
