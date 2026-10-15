<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { Subject, Task } from '@/api';
import { apiError } from '@/utils/apiError';
import { allMaterialChoices } from '@/composables/useMaterialChoices';
const { t } = useI18n();
const route = useRoute(), router = useRouter();
const rows = ref([]), subjects = ref([]), search = ref(''), subject = ref(''), page = ref(1);
const loading = ref(true), error = ref(''), subjectError = ref(''), hasNext = ref(false), total = ref(0);
const filtered = computed(() => Boolean(search.value.trim() || subject.value));
let request = 0, timer, disposed = false;
const scalar = value => typeof value === 'string' ? value : '';
async function load() {
  const current = ++request;
  loading.value = true; error.value = '';
  try {
    const result = await Task.filter({ title: search.value.trim(), ...(subject.value ? { subject: subject.value } : {}), page: page.value, page_size: 20, ordering: '-updated_at' });
    if (current !== request) return;
    rows.value = result.results ?? result;
    total.value = result.count ?? rows.value.length;
    hasNext.value = Boolean(result.links?.next);
  } catch (e) { if (current === request) error.value = apiError(e); }
  finally { if (current === request) loading.value = false; }
}
async function loadSubjects() {
  subjectError.value = '';
  try { const result = await allMaterialChoices(Subject, { is_active: true }); if (!disposed) subjects.value = result; }
  catch (e) { if (!disposed) subjectError.value = apiError(e); }
}
function syncRoute() {
  clearTimeout(timer);
  search.value = scalar(route.query.q);
  subject.value = /^\d+$/.test(scalar(route.query.subject)) ? route.query.subject : '';
  const parsedPage = Number(route.query.page);
  page.value = Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  load();
}
function applyFilters(nextPage = 1) {
  clearTimeout(timer);
  if (search.value.trim() === scalar(route.query.q) && subject.value === scalar(route.query.subject) && nextPage === page.value) {
    load();
    return;
  }
  router.replace({ query: { ...route.query, q: search.value.trim() || undefined, subject: subject.value || undefined, page: nextPage > 1 ? String(nextPage) : undefined } });
}
function queueSearch() {
  clearTimeout(timer);
  ++request;
  loading.value = true;
  timer = setTimeout(() => {
    // Whitespace-only edits can normalize to the same URL.
    if (search.value.trim() === scalar(route.query.q) && page.value === 1) load();
    else applyFilters();
  }, 250);
}
function clearFilters() { search.value = ''; subject.value = ''; applyFilters(); }
watch(() => [route.query.q, route.query.subject, route.query.page], syncRoute, { immediate: true });
onMounted(loadSubjects);
onBeforeUnmount(() => { disposed = true; clearTimeout(timer); ++request; });
</script>

<template>
  <section class="surface-card material-library" :aria-label="t('materialsFlow.library')">
    <div class="material-filters">
      <label class="material-search">{{ t('materialsFlow.search') }}<input v-model="search" class="form-control" type="search" :placeholder="t('materialsFlow.searchPlaceholder')" @input="queueSearch" /></label>
      <label>{{ t('materialsFlow.subject') }}<select v-model="subject" class="form-select" @change="applyFilters()"><option value="">{{ t('materialsFlow.allSubjects') }}</option><option v-for="item in subjects" :key="item.id" :value="String(item.id)">{{ item.name }}</option></select></label>
      <button v-if="filtered" class="btn btn-link clear-filters" @click="clearFilters">{{ t('materialsFlow.clearFilters') }}</button>
    </div>
    <div v-if="subjectError" class="alert alert-danger" role="alert">{{ subjectError }} <button class="btn btn-link" @click="loadSubjects">{{ t('ux.retry') }}</button></div>
    <div v-if="loading" class="library-loading" role="status">
      <span class="visually-hidden">{{ t('common.loading') }}</span>
      <div v-for="n in 3" :key="n" class="library-skeleton" aria-hidden="true"><span></span><span></span></div>
    </div>
    <div v-else-if="error" class="library-state" role="alert"><h2>{{ t('materialsFlow.loadFailed') }}</h2><p>{{ error }}</p><button class="btn btn-outline-primary" @click="load">{{ t('ux.retry') }}</button></div>
    <div v-else-if="!rows.length" class="library-state">
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 6h17l7 7v29H12zM28 6v9h8M18 23h12M18 29h12M18 35h7" /></svg>
      <h2>{{ t(filtered ? 'materialsFlow.noMatches' : 'materialsFlow.firstTest') }}</h2>
      <p>{{ t(filtered ? 'materialsFlow.noMatchesHint' : 'materialsFlow.firstTestHint') }}</p>
      <button v-if="filtered" class="btn btn-outline-primary" @click="clearFilters">{{ t('materialsFlow.clearFilters') }}</button>
      <router-link v-else class="btn btn-primary" :to="{ name: 'task-create' }">{{ t('materialsFlow.create') }}</router-link>
    </div>
    <template v-else>
      <div class="library-caption"><span role="status">{{ t('materialsFlow.total', { count: total }) }}</span><span class="library-state-label">{{ t('common.status') }}</span></div>
      <ul class="material-test-list">
        <li v-for="task in rows" :key="task.id">
          <router-link :to="{ name: 'task-workspace', params: { id: task.id }, query: { libraryQ: scalar(route.query.q) || undefined, librarySubject: subject || undefined, libraryPage: page > 1 ? String(page) : undefined } }" class="material-test-link">
            <span class="test-document" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3h8l4 4v14H6zM13 3v5h5M9 12h6M9 16h4" /></svg></span>
            <span class="test-copy"><span class="material-test-title">{{ task.title }}</span><span class="test-meta">{{ task.subject_name }}<span aria-hidden="true"> · </span>{{ t('materialsFlow.questions', { count: task.active_question_count }) }}</span></span>
            <span class="material-readiness" :class="{ ready: task.is_active && task.active_question_count >= task.questions_per_attempt }"><span class="status-dot" aria-hidden="true"></span>{{ t(!task.is_active ? 'common.inactive' : task.active_question_count >= task.questions_per_attempt ? 'materialsFlow.ready' : 'materialsFlow.draft') }}</span>
            <svg class="test-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
          </router-link>
        </li>
      </ul>
    </template>
    <nav v-if="!error && (page > 1 || hasNext)" class="material-pagination" :aria-label="t('materialsFlow.library')"><button class="btn btn-outline-secondary" :disabled="page === 1 || loading" @click="applyFilters(page - 1)">{{ t('materialsFlow.previous') }}</button><span>{{ t('materialsFlow.page', { page }) }}</span><button class="btn btn-outline-secondary" :disabled="!hasNext || loading" @click="applyFilters(page + 1)">{{ t('materialsFlow.nextPage') }}</button></nav>
  </section>
</template>

<style scoped>
.material-library { padding: 0 28px; }
.material-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 16px; padding: 24px 0; }
.material-filters label { display: grid; gap: 8px; font-size: 13px; font-weight: 500; min-width: 0; flex: 1 1 200px; }
.material-filters .material-search { flex: 2 1 260px; }
.clear-filters { font-size: 13px; }
.library-caption { display: flex; justify-content: space-between; padding: 14px 0; color: var(--ink-soft); border-top: 1px solid var(--line); font-size: 12px; }
.library-state-label { margin-right: 48px; }
.material-test-list { list-style: none; padding: 0; margin: 0; }
.material-test-list li { border-top: 1px solid var(--line); }
.material-test-link { display: grid; grid-template-columns: 40px minmax(0, 1fr) auto 20px; align-items: center; gap: 18px; padding: 22px 0; text-decoration: none; color: var(--ink); border-radius: 6px; transition: background-color var(--motion-fast); }
.material-test-link:hover { background: var(--surface-muted); }
.test-document { display: grid; place-items: center; width: 40px; height: 44px; background: var(--surface-muted); border-radius: 8px; color: var(--ink-soft); }
.test-document svg { width: 24px; height: 24px; }
.test-copy { min-width: 0; }
.material-test-title { display: block; font-size: 16px; font-weight: 600; overflow-wrap: anywhere; }
.test-meta { display: block; margin-top: 6px; color: var(--ink-soft); font-size: 13px; overflow-wrap: anywhere; }
.material-readiness { display: flex; align-items: center; gap: 7px; color: var(--ink-soft); font-size: 12px; }
.material-readiness.ready { color: var(--success); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.test-arrow { width: 20px; height: 20px; color: var(--ink-soft); }
.material-pagination { display: flex; justify-content: flex-end; align-items: center; gap: 16px; padding: 20px 0; border-top: 1px solid var(--line); }
.library-state { padding: 48px 16px 56px; text-align: center; border-top: 1px solid var(--line); }
.library-state > svg { width: 48px; height: 48px; color: var(--ink-soft); margin-bottom: 20px; }
.library-state h2 { font-size: 20px; margin: 0 0 10px; }
.library-state p { color: var(--ink-soft); max-width: 48ch; margin: 0 auto 24px; }
.library-skeleton { padding: 26px 0; border-top: 1px solid var(--line); display: grid; gap: 12px; }
.library-skeleton span { background: var(--bg-1); height: 14px; border-radius: 4px; width: 55%; }
.library-skeleton span + span { width: 30%; height: 10px; }
@media (max-width: 640px) {
  .material-library { padding: 0 16px; }
  .material-filters { gap: 12px; padding: 20px 0; }
  .material-test-link { grid-template-columns: 32px minmax(0, 1fr) 16px; gap: 10px 12px; padding: 20px 0; }
  .test-document { width: 32px; height: 38px; align-self: start; }
  .material-readiness { grid-column: 2; grid-row: 2; }
  .test-arrow { grid-column: 3; grid-row: 1; width: 16px; }
  .library-state-label { display: none; }
  .material-pagination { gap: 8px; justify-content: space-between; font-size: 12px; }
  .material-pagination .btn { padding-inline: 10px; }
  .library-state { padding: 32px 0; }
}
</style>
