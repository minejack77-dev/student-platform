import { onBeforeUnmount, onMounted, ref } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

// Only guard data that cannot be restored from the existing session draft.
export function useUnsavedChanges(isDirty, isBlocked = () => false) {
  const auth = useAuthStore();
  const pendingLeave = ref(false);
  let resolveLeave;
  const requestLeave = (force = false) => {
    if (isBlocked()) return Promise.resolve(false);
    if (!auth.user || (!force && !isDirty())) return Promise.resolve(true);
    if (resolveLeave) return Promise.resolve(false);
    pendingLeave.value = true;
    return new Promise(resolve => { resolveLeave = resolve; });
  };
  const finishLeave = (allowed) => {
    pendingLeave.value = false;
    resolveLeave?.(allowed);
    resolveLeave = undefined;
  };
  const guardAction = async (action, force = false) => {
    if (await requestLeave(force)) action();
  };
  const beforeUnload = (event) => {
    if (auth.user && (isDirty() || isBlocked())) {
      event.preventDefault();
      event.returnValue = '';
    }
  };
  onBeforeRouteLeave(() => requestLeave());
  onMounted(() => window.addEventListener('beforeunload', beforeUnload));
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', beforeUnload);
    finishLeave(false);
  });
  return { pendingLeave, finishLeave, guardAction };
}
