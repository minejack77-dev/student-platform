<script setup>
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import axios from 'axios';
import { Group } from '@/api';
import { apiError } from '@/utils/apiError';
import { allMaterialChoices } from '@/composables/useMaterialChoices';
const props = defineProps({ task: { type: Object, required: true }, blocked: Boolean });
const emit = defineEmits(['busy']);
const { t, locale } = useI18n();
const groups = ref([]), group = ref(''), date = ref(''), loading = ref(true), saving = ref(false), error = ref(''), result = ref(null);
const today = new Date();
const minimumDate = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
date.value = minimumDate;
const ready = computed(() => props.task.is_active && props.task.active_question_count >= props.task.questions_per_attempt);
const summary = computed(() => t('materialsFlow.summary', { title: props.task.title, group: groups.value.find(item => String(item.id) === String(group.value))?.name || '—', date: date.value ? new Intl.DateTimeFormat(locale.value, { dateStyle: 'long' }).format(new Date(`${date.value}T12:00:00`)) : '—' }));
async function load() {
  loading.value = true; error.value = '';
  try { groups.value = await allMaterialChoices(Group, { is_active: true }); }
  catch (e) { error.value = apiError(e); }
  finally { loading.value = false; }
}
async function assign() {
  if (saving.value || props.blocked || !ready.value) return;
  if (!group.value || !date.value) { error.value = t('materialsFlow.chooseBoth'); return; }
  saving.value = true; emit('busy', true); error.value = '';
  try { const response = await axios.post(`/api/task/${props.task.id}/assign/`, { group: Number(group.value), date: date.value }); result.value = { ...response.data, summary: summary.value }; }
  catch (e) { error.value = apiError(e); }
  finally { saving.value = false; emit('busy', false); }
}
onMounted(load);
</script>
<template>
  <section class="surface-card assignment-panel">
    <h2>{{ t('materialsFlow.assign') }}</h2>
    <div v-if="result" role="status"><h3>{{ t('materialsFlow.assigned') }}</h3><p>{{ result.summary }}</p><router-link class="btn btn-primary" :to="{ name: 'group-overview', params: { id: result.group }, query: { date: result.scheduled_for } }">{{ t('materialsFlow.schedule') }}</router-link></div>
    <template v-else>
      <p>{{ t('materialsFlow.assignHint') }}</p>
      <p v-if="!ready" class="alert alert-warning">{{ t('materialsFlow.notReady') }}</p>
      <p v-if="blocked" class="alert alert-warning">{{ t('materialsFlow.savedQuestion') }}</p>
      <p v-if="loading" role="status">{{ t('common.loading') }}</p>
      <form v-else @submit.prevent="assign"><fieldset :disabled="saving || blocked || !ready">
        <div class="assignment-fields"><label>{{ t('materialsFlow.group') }}<select v-model="group" required class="form-select"><option value="" disabled>{{ t('materialsFlow.chooseGroup') }}</option><option v-for="item in groups" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>{{ t('materialsFlow.date') }}<input v-model="date" class="form-control" type="date" :min="minimumDate" required /></label></div>
        <p v-if="!groups.length">{{ t('materialsFlow.noGroups') }}</p>
        <p v-if="group && date" class="assignment-summary">{{ summary }}</p>
        <button class="btn btn-primary" :disabled="!groups.length">{{ saving ? t('common.saving') : t('materialsFlow.confirm') }}</button>
      </fieldset></form>
      <div v-if="error" class="alert alert-danger mt-3" role="alert">{{ error }} <button v-if="!groups.length" class="btn btn-link" @click="load">{{ t('ux.retry') }}</button></div>
    </template>
  </section>
</template>
<style scoped>
.assignment-panel { padding:24px; margin:20px 0; }
h2 { font-size:22px; } h3 { font-size:18px; margin:24px 0 8px; }
.assignment-fields { display:grid; grid-template-columns:1fr 1fr; gap:20px; max-width:720px; margin:24px 0; }
label { display:grid; gap:8px; }
.assignment-summary { font-weight:600; margin:24px 0; overflow-wrap:anywhere; }
@media(max-width:600px) { .assignment-fields { grid-template-columns:1fr; } }
</style>
