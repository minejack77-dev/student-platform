<script setup>
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Task } from '@/api';
import { apiError } from '@/utils/apiError';
import TopicDetail from './TopicDetail.vue';
const props = defineProps({ id: { type: String, required: true } });
const { t } = useI18n();
const task = ref(null), loading = ref(true), error = ref('');
async function load() {
  loading.value = true; error.value = '';
  try { task.value = await Task.get(props.id); }
  catch (e) { error.value = apiError(e); }
  finally { loading.value = false; }
}
onMounted(load);
</script>
<template>
  <p v-if="loading" role="status">{{ t('common.loading') }}</p>
  <div v-else-if="error" class="alert alert-danger" role="alert">{{ error }} <button class="btn btn-link" @click="load">{{ t('ux.retry') }}</button></div>
  <TopicDetail v-else-if="task" :id="String(task.topic)" :task-id="String(task.id)" workspace />
</template>
