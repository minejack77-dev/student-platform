<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
defineProps({ title: String, message: String, description: String, confirmLabel: String, cancelLabel: String });
const emit = defineEmits(['confirm', 'cancel']);
const dialog = ref(null);
let previousFocus;
onMounted(() => { previousFocus = document.activeElement; dialog.value.showModal(); });
onBeforeUnmount(() => previousFocus?.focus?.());
</script>
<template>
  <dialog ref="dialog" class="confirm-dialog" aria-labelledby="confirmation-title" @cancel.prevent="emit('cancel')">
    <h2 id="confirmation-title">{{ title }}</h2>
    <p>{{ message || description }}</p>
    <div class="dialog-actions">
      <button class="btn btn-outline-primary" autofocus @click="emit('cancel')">{{ cancelLabel || t('common.cancel') }}</button>
      <button class="btn btn-primary" @click="emit('confirm')">{{ confirmLabel }}</button>
    </div>
  </dialog>
</template>
<style scoped>
.confirm-dialog { width: min(560px, calc(100vw - 32px)); max-width: none; border: 1px solid var(--line); border-radius: var(--radius-xl); padding: 28px; color: var(--ink); background: var(--surface-strong); box-shadow: var(--shadow-1); }
.confirm-dialog h2 { font-size: 24px; margin: 0 0 12px; }
.confirm-dialog p { color: var(--ink-soft); line-height: 1.65; margin: 0 0 24px; }
.confirm-dialog::backdrop { background: rgba(16, 30, 52, .4); backdrop-filter: blur(4px); }
.dialog-actions { display: flex; flex-wrap: wrap; gap: 12px; justify-content: flex-end; }
.dialog-actions .btn { min-height: 44px; }
@media (max-width: 480px) { .confirm-dialog { padding: 20px; } .dialog-actions .btn { flex: 1 1 100%; } }
</style>
