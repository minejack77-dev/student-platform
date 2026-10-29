<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from "vue";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: "" },
  label: { type: String, required: true },
  disabled: Boolean,
});
const emit = defineEmits(["update:modelValue", "open"]);
const id = useId();
const root = ref(null);
const trigger = ref(null);
const list = ref(null);
const opened = ref(false);
const activeValue = ref("");
const popupStyle = ref({});
const selected = computed(() => props.options.find(option => option.value === props.modelValue));
const enabled = computed(() => props.options.filter(option => !option.disabled));
const optionId = value => `${id}-option-${value}`;

const positionPopup = () => {
  if (!opened.value || !trigger.value) return;
  const rect = trigger.value.getBoundingClientRect();
  const margin = 8;
  const gap = 4;
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = window.innerHeight;
  const below = Math.max(0, viewportHeight - rect.bottom - gap - margin);
  const above = Math.max(0, rect.top - gap - margin);
  const preferredHeight = Math.min(240, viewportHeight * 0.4);
  const upwards = below < preferredHeight && above > below;
  const height = Math.min(preferredHeight, upwards ? above : below);
  const width = Math.min(rect.width, viewportWidth - margin * 2);
  popupStyle.value = {
    left: `${Math.max(margin, Math.min(rect.left, viewportWidth - width - margin))}px`,
    top: `${upwards ? rect.top - gap - height : rect.bottom + gap}px`,
    width: `${width}px`, height: `${height}px`,
  };
};

const revealActive = async () => {
  await nextTick();
  const option = document.getElementById(optionId(activeValue.value));
  if (!option || !list.value) return;
  const top = option.offsetTop;
  const bottom = top + option.offsetHeight;
  if (top < list.value.scrollTop) list.value.scrollTop = top;
  else if (bottom > list.value.scrollTop + list.value.clientHeight) {
    list.value.scrollTop = bottom - list.value.clientHeight;
  }
};
const close = (restoreFocus = false) => {
  opened.value = false;
  if (restoreFocus) trigger.value?.focus();
};
const open = async (fromEnd = false) => {
  if (props.disabled || opened.value) return;
  opened.value = true;
  positionPopup();
  activeValue.value = enabled.value.find(option => option.value === props.modelValue)?.value
    ?? (fromEnd ? enabled.value.at(-1)?.value : enabled.value[0]?.value) ?? "";
  emit("open");
  await nextTick();
  list.value?.focus();
  revealActive();
};
const choose = option => {
  if (!option || option.disabled) return;
  emit("update:modelValue", option.value);
  close(true);
};
const onKeydown = event => {
  if (event.key === "Escape") { event.preventDefault(); close(true); return; }
  if (event.key === "Tab") { close(true); return; }
  if (["Enter", " "].includes(event.key)) {
    event.preventDefault();
    choose(enabled.value.find(option => option.value === activeValue.value));
    return;
  }
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const options = enabled.value;
  if (!options.length) return;
  const index = options.findIndex(option => option.value === activeValue.value);
  const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
    : Math.max(0, Math.min(options.length - 1, index + (event.key === "ArrowDown" ? 1 : -1)));
  activeValue.value = options[next].value;
  revealActive();
};
watch(enabled, options => {
  if (opened.value && !options.some(option => option.value === activeValue.value)) {
    activeValue.value = options[0]?.value ?? "";
  }
});
watch(() => props.disabled, disabled => { if (disabled) close(); });
const onOutsideInteraction = event => {
  if (!root.value?.contains(event.target) && !list.value?.contains(event.target)) close();
};
const onScroll = event => {
  if (!list.value?.contains(event.target)) positionPopup();
};
onMounted(() => {
  document.addEventListener("pointerdown", onOutsideInteraction);
  document.addEventListener("focusin", onOutsideInteraction);
  window.addEventListener("scroll", onScroll, true);
  window.addEventListener("resize", positionPopup);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onOutsideInteraction);
  document.removeEventListener("focusin", onOutsideInteraction);
  window.removeEventListener("scroll", onScroll, true);
  window.removeEventListener("resize", positionPopup);
});
</script>

<template>
  <div ref="root" class="scrollable-select">
    <button
      ref="trigger" type="button" class="form-select form-select-sm scrollable-select-trigger"
      :disabled="disabled" :aria-label="label" aria-haspopup="listbox"
      :aria-expanded="opened" :aria-controls="`${id}-list`"
      @click="opened ? close() : open()"
      @keydown.down.prevent="open()" @keydown.up.prevent="open(true)"
    >{{ selected?.label || placeholder }}</button>
    <Teleport to="body">
    <div
      v-if="opened" :id="`${id}-list`" ref="list" class="scrollable-select-list"
      :style="popupStyle"
      role="listbox" tabindex="-1" :aria-label="label"
      :aria-activedescendant="activeValue ? optionId(activeValue) : undefined"
      @keydown="onKeydown"
    >
      <div v-if="!options.length" class="scrollable-select-empty">{{ placeholder }}</div>
      <div
        v-for="option in options" :id="optionId(option.value)" :key="option.value"
        role="option" class="scrollable-select-option"
        :class="{ 'is-active': option.value === activeValue, 'is-disabled': option.disabled }"
        :aria-selected="option.value === modelValue" :aria-disabled="Boolean(option.disabled)"
        @mousedown.prevent @click="choose(option)"
      >{{ option.label }}</div>
    </div>
    </Teleport>
  </div>
</template>

<style scoped>
.scrollable-select { position: relative; min-width: 0; }
.scrollable-select-trigger { text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scrollable-select-list {
  position: fixed; z-index: 10000; box-sizing: border-box; overflow-y: auto;
  overscroll-behavior: contain; scrollbar-gutter: stable;
  border: 1px solid #b8c5d8; border-radius: 8px; background: #fff;
  box-shadow: 0 8px 24px #152b4d26; padding: 4px; outline-offset: 2px;
}
.scrollable-select-option, .scrollable-select-empty { padding: 7px 9px; font-size: .875rem; overflow-wrap: anywhere; }
.scrollable-select-option { cursor: pointer; border-radius: 4px; }
.scrollable-select-option:hover:not(.is-disabled), .scrollable-select-option.is-active { background: #e8f0ff; }
.scrollable-select-option[aria-selected="true"] { font-weight: 600; }
.scrollable-select-option.is-disabled { color: #687588; cursor: not-allowed; }
</style>
