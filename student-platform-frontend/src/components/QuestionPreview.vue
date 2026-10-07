<script setup>
import { onMounted, onBeforeUnmount, onUnmounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { sanitizeInlineRichText } from '@/utils/richText';
import QuestionImageGallery from './QuestionImageGallery.vue';
defineProps({ question: { type: Object, required: true } });
const emit = defineEmits(['close']);
const { t } = useI18n();
const dialog = ref(null);
let previousFocus;
onMounted(() => { previousFocus = document.activeElement; dialog.value.showModal(); });
onBeforeUnmount(() => dialog.value?.close());
onUnmounted(() => { if (previousFocus?.isConnected) previousFocus.focus(); });
</script>
<template>
  <dialog ref="dialog" aria-labelledby="question-preview-title" @cancel.prevent="emit('close')">
    <div class="preview-header"><h2 id="question-preview-title">{{ t('materialsFlow.preview') }}</h2><button class="btn btn-outline-primary" autofocus @click="emit('close')">{{ t('materialsFlow.close') }}</button></div>
    <p>{{ t('materialsFlow.previewHint') }}</p>
    <div class="preview-text" v-html="sanitizeInlineRichText(question.text)" />
    <div v-if="question.instruction" v-html="sanitizeInlineRichText(question.instruction)" />
    <QuestionImageGallery :images="question.images || []" />
    <div v-if="question.question_type === 'matching'" class="preview-matching"><ul><li v-for="(pair, index) in question.matching_pairs" :key="index" v-html="sanitizeInlineRichText(pair.left_content)" /></ul><ul><li v-for="(pair, index) in [...question.matching_pairs].reverse()" :key="index" v-html="sanitizeInlineRichText(pair.right_content)" /></ul></div>
    <fieldset v-else><label v-for="(choice, index) in question.choices" :key="index"><input :type="question.question_type === 'single_choice' ? 'radio' : 'checkbox'" name="preview-answer" /><span v-html="sanitizeInlineRichText(choice.text)" /></label></fieldset>
  </dialog>
</template>
<style scoped>
dialog { width:min(760px,calc(100vw - 32px)); max-height:85vh; padding:28px; border:1px solid var(--line); border-radius:12px; color:var(--ink); }
dialog::backdrop { background:rgb(16 30 52 / 40%); }
.preview-header { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
h2 { font-size:22px; margin:0; } p { color:var(--ink-soft); margin:20px 0; }
.preview-text { font-size:18px; margin:24px 0 16px; overflow-wrap:anywhere; }
label { display:flex; align-items:baseline; gap:12px; padding:12px 0; }
.preview-matching { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.preview-matching li { padding:8px 0; overflow-wrap:anywhere; }
</style>
