<script setup>
import { onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { Subject, Topic } from '@/api';
import { apiError } from '@/utils/apiError';
import { allMaterialChoices } from '@/composables/useMaterialChoices';
import { useUnsavedChanges } from '@/composables/useUnsavedChanges';
import ConfirmDialog from '@/components/ConfirmDialog.vue';
const { t } = useI18n();
const router = useRouter();
const title = ref(''), subject = ref(''), topic = ref(''), subjects = ref([]), topics = ref([]);
const error = ref(''), loading = ref(true), saving = ref(false), completed = ref(false), topicsLoading = ref(false);
const { pendingLeave, finishLeave } = useUnsavedChanges(() => !completed.value && Boolean(title.value || subject.value), () => saving.value);
async function load() {
  loading.value = true; error.value = '';
  try { subjects.value = await allMaterialChoices(Subject, { is_active: true }); }
  catch (e) { error.value = apiError(e); }
  finally { loading.value = false; }
}
let request = 0;
watch(subject, async (value) => {
  const current = ++request;
  topic.value = ''; topics.value = []; error.value = '';
  if (!value) { topicsLoading.value = false; return; }
  topicsLoading.value = true;
  try { const result = await allMaterialChoices(Topic, { subject: value, is_active: true }); if (request === current) topics.value = result; }
  catch (e) { if (request === current) error.value = apiError(e); }
  finally { if (request === current) topicsLoading.value = false; }
});
async function submit() {
  if (saving.value) return;
  saving.value = true; error.value = '';
  try {
    const { data } = await axios.post('/api/task/quick-create/', { title: title.value.trim(), subject: Number(subject.value), ...(topic.value ? { topic: Number(topic.value) } : {}) });
    completed.value = true; saving.value = false;
    await router.push({ name: 'task-workspace', params: { id: data.id } });
  } catch (e) { error.value = apiError(e); }
  finally { saving.value = false; }
}
onMounted(load);
</script>
<template>
  <div class="material-create">
    <router-link :to="{ name: 'teacher-home', query: { view: 'materials' } }">{{ t('materialsFlow.library') }}</router-link>
    <h1>{{ t('materialsFlow.create') }}</h1><p>{{ t('materialsFlow.createHint') }}</p>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <form v-else class="surface-card material-create-form" @submit.prevent="submit">
      <fieldset :disabled="saving">
        <label for="test-title">{{ t('materialsFlow.title') }}</label><input id="test-title" v-model="title" required maxlength="200" class="form-control" :placeholder="t('materialsFlow.titleHint')" />
        <label for="test-subject">{{ t('materialsFlow.subject') }}</label><select id="test-subject" v-model="subject" required class="form-select"><option value="" disabled>{{ t('materialsFlow.chooseSubject') }}</option><option v-for="item in subjects" :key="item.id" :value="item.id">{{ item.name }}</option></select>
        <p v-if="!subjects.length">{{ t('materialsFlow.noSubjects') }} <router-link :to="{ name: 'teacher-home', query: { view: 'materials', organize: '1' } }">{{ t('materialsFlow.subjects') }}</router-link></p>
        <details><summary>{{ t('materialsFlow.optional') }}</summary><label for="test-topic">{{ t('materialsFlow.optional') }}</label><select id="test-topic" v-model="topic" class="form-select" :disabled="!subject || topicsLoading"><option value="">{{ t('materialsFlow.automatic') }}</option><option v-for="item in topics" :key="item.id" :value="item.id">{{ item.workbook_title }} / {{ item.unit_title }} / {{ item.title }}</option></select></details>
        <div v-if="error" class="alert alert-danger" role="alert">{{ error }} <button type="button" v-if="!subjects.length" class="btn btn-link" @click="load">{{ t('ux.retry') }}</button></div>
        <button class="btn btn-primary" :disabled="!subjects.length || topicsLoading">{{ saving ? t('common.saving') : t('materialsFlow.next') }}</button>
      </fieldset>
    </form>
    <ConfirmDialog v-if="pendingLeave" :title="t('workstation.materials.leaveTitle')" :description="t('workstation.materials.leaveHint')" :confirm-label="t('workstation.materials.leave')" @cancel="finishLeave(false)" @confirm="finishLeave(true)" />
  </div>
</template>
<style scoped>
.material-create { max-width:760px; margin:auto; }
h1 { margin:24px 0 12px; font-size:30px; }
p { color:var(--ink-soft); }
.material-create-form { margin-top:28px; padding:28px; }
fieldset { display:grid; gap:10px; }
label:not(:first-child), details { margin-top:16px; }
details label { display:block; margin:16px 0 8px; }
button[type], button.btn-primary { margin-top:16px; justify-self:start; }
@media(max-width:600px) { .material-create-form { padding:16px; } }
</style>
