<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Subject, Task } from '@/api';
import { apiError } from '@/utils/apiError';
import { allMaterialChoices } from '@/composables/useMaterialChoices';
const { t } = useI18n();
const rows = ref([]), subjects = ref([]), search = ref(''), subject = ref(''), page = ref(1);
const loading = ref(true), error = ref(''), hasNext = ref(false);
let request = 0, timer;
async function load() {
  const current = ++request;
  loading.value = true; error.value = '';
  try {
    const result = await Task.filter({ title: search.value, ...(subject.value ? { subject: subject.value } : {}), page: page.value, page_size: 20, ordering: '-updated_at' });
    if (current !== request) return;
    rows.value = result.results ?? result;
    hasNext.value = Boolean(result.links?.next);
  } catch (e) { if (current === request) error.value = apiError(e); }
  finally { if (current === request) loading.value = false; }
}
watch([search, subject], () => { clearTimeout(timer); ++request; loading.value = true; timer = setTimeout(() => { page.value = 1; load(); }, 250); });
watch(page, load);
onMounted(async () => {
  await load();
  try { subjects.value = await allMaterialChoices(Subject, { is_active: true }); }
  catch (e) { error.value = apiError(e); }
});
onBeforeUnmount(() => { clearTimeout(timer); ++request; });
</script>

<template>
  <section class="surface-card material-library">
    <div class="material-library-head"><h2>{{ t('materialsFlow.library') }}</h2><router-link class="btn btn-primary" :to="{ name: 'task-create' }">{{ t('materialsFlow.create') }}</router-link></div>
    <div class="material-filters">
      <label>{{ t('materialsFlow.search') }}<input v-model="search" class="form-control" type="search" /></label>
      <label>{{ t('materialsFlow.subject') }}<select v-model="subject" class="form-select"><option value="">{{ t('materialsFlow.allSubjects') }}</option><option v-for="item in subjects" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
    </div>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-else-if="error" class="alert alert-danger" role="alert">{{ error }} <button class="btn btn-link" @click="load">{{ t('ux.retry') }}</button></div>
    <p v-else-if="!rows.length" class="empty-box">{{ t('materialsFlow.empty') }}</p>
    <ul v-else class="material-test-list">
      <li v-for="task in rows" :key="task.id">
        <div><router-link :to="{ name: 'task-workspace', params: { id: task.id } }" class="material-test-title">{{ task.title }}</router-link><p>{{ task.subject_name }} · {{ t('materialsFlow.questions', { count: task.active_question_count }) }}</p></div>
        <span class="material-readiness" :class="{ ready: task.is_active && task.active_question_count >= task.questions_per_attempt }">{{ t(!task.is_active ? 'common.inactive' : task.active_question_count >= task.questions_per_attempt ? 'materialsFlow.ready' : 'materialsFlow.draft') }}</span>
      </li>
    </ul>
    <nav class="material-pagination" :aria-label="t('materialsFlow.library')"><button class="btn btn-outline-primary" :disabled="page === 1 || loading" @click="page--">{{ t('materialsFlow.previous') }}</button><span>{{ t('materialsFlow.page', { page }) }}</span><button class="btn btn-outline-primary" :disabled="!hasNext || loading" @click="page++">{{ t('materialsFlow.nextPage') }}</button></nav>
  </section>
</template>

<style scoped>
.material-library { padding: 24px; }
.material-library-head { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
h2 { font-size:20px; margin:0; }
.material-filters { display:grid; grid-template-columns:2fr 1fr; gap:16px; margin:24px 0; }
label { display:grid; gap:6px; }
.material-test-list { list-style:none; padding:0; margin:0; }
.material-test-list li { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:20px 0; border-top:1px solid var(--line); }
.material-test-title { font-size:16px; font-weight:650; overflow-wrap:anywhere; }
p { margin:6px 0 0; color:var(--ink-soft); }
.material-readiness { color:var(--ink-soft); white-space:nowrap; font-size:13px; }
.material-readiness.ready { color:var(--success); }
.material-pagination { display:flex; justify-content:flex-end; align-items:center; gap:16px; margin-top:24px; }
@media(max-width:600px) { .material-library { padding:16px; } .material-filters { grid-template-columns:1fr; } .material-test-list li { align-items:flex-start; flex-direction:column; gap:6px; } }
</style>
