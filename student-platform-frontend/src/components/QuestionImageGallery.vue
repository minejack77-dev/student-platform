<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps({
  images: {
    type: Array,
    default: () => [],
  },
  compact: {
    type: Boolean,
    default: false,
  },
  removable: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["remove"]);

const { t } = useI18n();
const isOpen = ref(false);
const currentIndex = ref(0);
const scale = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);
const pointers = new Map();
let panStart = null;
let pinchStart = null;
let previousBodyOverflow = "";

const currentImage = computed(() => props.images[currentIndex.value] ?? null);
const imageTransform = computed(
  () => `translate3d(${offsetX.value}px, ${offsetY.value}px, 0) scale(${scale.value})`,
);
const zoomLabel = computed(() => `${Math.round(scale.value * 100)}%`);

const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

const clampOffsets = () => {
  if (scale.value <= 1) {
    offsetX.value = 0;
    offsetY.value = 0;
    return;
  }
  const maxX = (window.innerWidth * (scale.value - 1)) / 2;
  const maxY = (window.innerHeight * (scale.value - 1)) / 2;
  offsetX.value = clamp(offsetX.value, -maxX, maxX);
  offsetY.value = clamp(offsetY.value, -maxY, maxY);
};

const resetView = () => {
  scale.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
  pointers.clear();
  panStart = null;
  pinchStart = null;
};

const openImage = (index) => {
  currentIndex.value = index;
  resetView();
  isOpen.value = true;
};

const close = () => {
  isOpen.value = false;
  resetView();
};

const showRelativeImage = (direction) => {
  if (props.images.length < 2) {
    return;
  }
  currentIndex.value =
    (currentIndex.value + direction + props.images.length) % props.images.length;
  resetView();
};

const setScale = (nextScale) => {
  scale.value = clamp(nextScale, 1, 5);
  clampOffsets();
};

const zoomBy = (amount) => {
  setScale(scale.value + amount);
};

const onWheel = (event) => {
  zoomBy(event.deltaY < 0 ? 0.25 : -0.25);
};

const pointerDistance = () => {
  const [first, second] = [...pointers.values()];
  return Math.hypot(second.x - first.x, second.y - first.y);
};

const pointerCenter = () => {
  const [first, second] = [...pointers.values()];
  return {
    x: (first.x + second.x) / 2,
    y: (first.y + second.y) / 2,
  };
};

const startPinch = () => {
  const center = pointerCenter();
  pinchStart = {
    distance: pointerDistance(),
    scale: scale.value,
    centerX: center.x,
    centerY: center.y,
    offsetX: offsetX.value,
    offsetY: offsetY.value,
  };
  panStart = null;
};

const onPointerDown = (event) => {
  event.currentTarget.setPointerCapture?.(event.pointerId);
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
  if (pointers.size === 2) {
    startPinch();
  } else if (pointers.size === 1 && scale.value > 1) {
    panStart = {
      x: event.clientX,
      y: event.clientY,
      offsetX: offsetX.value,
      offsetY: offsetY.value,
    };
  }
};

const onPointerMove = (event) => {
  if (!pointers.has(event.pointerId)) {
    return;
  }
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

  if (pointers.size === 2 && pinchStart) {
    const center = pointerCenter();
    scale.value = clamp(
      pinchStart.scale * (pointerDistance() / Math.max(pinchStart.distance, 1)),
      1,
      5,
    );
    offsetX.value = pinchStart.offsetX + center.x - pinchStart.centerX;
    offsetY.value = pinchStart.offsetY + center.y - pinchStart.centerY;
    clampOffsets();
  } else if (pointers.size === 1 && panStart && scale.value > 1) {
    offsetX.value = panStart.offsetX + event.clientX - panStart.x;
    offsetY.value = panStart.offsetY + event.clientY - panStart.y;
    clampOffsets();
  }
};

const onPointerUp = (event) => {
  pointers.delete(event.pointerId);
  pinchStart = null;
  if (pointers.size === 1 && scale.value > 1) {
    const remaining = [...pointers.values()][0];
    panStart = {
      x: remaining.x,
      y: remaining.y,
      offsetX: offsetX.value,
      offsetY: offsetY.value,
    };
  } else {
    panStart = null;
  }
};

const onDoubleClick = () => {
  if (scale.value > 1) {
    resetView();
  } else {
    setScale(2);
  }
};

const onKeydown = (event) => {
  if (event.key === "Escape") {
    close();
  } else if (event.key === "ArrowLeft") {
    showRelativeImage(-1);
  } else if (event.key === "ArrowRight") {
    showRelativeImage(1);
  } else if (event.key === "+" || event.key === "=") {
    zoomBy(0.25);
  } else if (event.key === "-") {
    zoomBy(-0.25);
  }
};

watch(isOpen, (open) => {
  if (open) {
    previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeydown);
  } else {
    document.body.style.overflow = previousBodyOverflow;
    window.removeEventListener("keydown", onKeydown);
  }
});

watch(
  () => props.images.length,
  (length) => {
    if (currentIndex.value >= length) {
      currentIndex.value = Math.max(0, length - 1);
    }
    if (length === 0) {
      close();
    }
  },
);

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  if (isOpen.value) {
    document.body.style.overflow = previousBodyOverflow;
  }
});
</script>

<template>
  <div
    v-if="images.length"
    class="question-image-gallery"
    :class="{ compact, single: images.length === 1 }"
  >
    <div
      v-for="(image, index) in images"
      :key="image.id ?? image.image"
      class="question-image-thumbnail-wrap"
    >
      <button
        class="question-image-thumbnail"
        type="button"
        :aria-label="t('imageViewer.open')"
        @click="openImage(index)"
      >
        <img
          :src="image.image"
          :alt="image.original_name || t('imageViewer.image')"
          loading="lazy"
        />
        <span v-if="compact && image.original_name" :title="image.original_name">
          {{ image.original_name }}
        </span>
      </button>
      <button
        v-if="removable"
        class="thumbnail-remove"
        type="button"
        :aria-label="t('common.remove')"
        :title="t('common.remove')"
        :disabled="disabled"
        @click="emit('remove', image)"
      >
        &times;
      </button>
    </div>
  </div>

  <Teleport to="body">
    <div
      v-if="isOpen && currentImage"
      class="image-lightbox"
      role="dialog"
      aria-modal="true"
      :aria-label="t('imageViewer.dialog')"
      @click.self="close"
    >
      <div class="image-lightbox-toolbar">
        <button
          type="button"
          :aria-label="t('imageViewer.zoomOut')"
          :title="t('imageViewer.zoomOut')"
          :disabled="scale <= 1"
          @click="zoomBy(-0.25)"
        >
          &minus;
        </button>
        <button
          class="zoom-value"
          type="button"
          :aria-label="t('imageViewer.resetZoom')"
          :title="t('imageViewer.resetZoom')"
          :disabled="scale === 1"
          @click="resetView"
        >
          {{ zoomLabel }}
        </button>
        <button
          type="button"
          :aria-label="t('imageViewer.zoomIn')"
          :title="t('imageViewer.zoomIn')"
          :disabled="scale >= 5"
          @click="zoomBy(0.25)"
        >
          +
        </button>
        <button
          class="close-button"
          type="button"
          :aria-label="t('imageViewer.close')"
          :title="t('imageViewer.close')"
          @click="close"
        >
          &times;
        </button>
      </div>

      <button
        v-if="images.length > 1"
        class="image-nav previous"
        type="button"
        :aria-label="t('imageViewer.previous')"
        :title="t('imageViewer.previous')"
        @click="showRelativeImage(-1)"
      >
        &#8249;
      </button>

      <div
        class="image-lightbox-stage"
        :class="{ zoomed: scale > 1 }"
        @wheel.prevent="onWheel"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @dblclick="onDoubleClick"
        @click.self="close"
      >
        <img
          :src="currentImage.image"
          :alt="currentImage.original_name || t('imageViewer.image')"
          :style="{ transform: imageTransform }"
          draggable="false"
        />
      </div>

      <button
        v-if="images.length > 1"
        class="image-nav next"
        type="button"
        :aria-label="t('imageViewer.next')"
        :title="t('imageViewer.next')"
        @click="showRelativeImage(1)"
      >
        &#8250;
      </button>

      <div v-if="images.length > 1" class="image-counter">
        {{ t("imageViewer.counter", { current: currentIndex + 1, total: images.length }) }}
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.question-image-gallery {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
  margin: 0 0 18px;
  max-width: 920px;
}

.question-image-gallery.single {
  grid-template-columns: minmax(0, 720px);
}

.question-image-thumbnail {
  align-items: center;
  background: rgba(16, 39, 64, 0.04);
  border: 1px solid rgba(16, 39, 64, 0.1);
  border-radius: var(--radius-md);
  cursor: zoom-in;
  display: flex;
  justify-content: center;
  min-height: 180px;
  overflow: hidden;
  padding: 0;
  width: 100%;
}

.question-image-thumbnail-wrap {
  min-width: 0;
  position: relative;
}

.thumbnail-remove {
  align-items: center;
  background: rgba(157, 39, 39, 0.92);
  border: 2px solid #fff;
  border-radius: 50%;
  color: #fff;
  display: flex;
  font-size: 20px;
  height: 32px;
  justify-content: center;
  padding: 0;
  position: absolute;
  right: 7px;
  top: 7px;
  width: 32px;
  z-index: 2;
}

.thumbnail-remove:disabled {
  opacity: 0.55;
}

.question-image-thumbnail img {
  display: block;
  height: auto;
  max-height: 520px;
  max-width: 100%;
  object-fit: contain;
}

.question-image-gallery.compact {
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  margin: 14px 0;
  max-width: 760px;
}

.compact .question-image-thumbnail {
  display: grid;
  grid-template-rows: 130px auto;
  min-height: 0;
}

.compact .question-image-thumbnail img {
  height: 130px;
  width: 100%;
}

.compact .question-image-thumbnail span {
  color: var(--ink-soft);
  font-size: 12px;
  overflow: hidden;
  padding: 7px 8px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-lightbox {
  background: rgba(5, 9, 14, 0.96);
  inset: 0;
  overflow: hidden;
  position: fixed;
  z-index: 3000;
}

.image-lightbox-toolbar {
  align-items: center;
  display: flex;
  gap: 8px;
  padding: max(10px, env(safe-area-inset-top)) max(10px, env(safe-area-inset-right)) 10px;
  position: absolute;
  right: 0;
  top: 0;
  z-index: 3;
}

.image-lightbox-toolbar button,
.image-nav {
  align-items: center;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 50%;
  color: #fff;
  display: inline-flex;
  font-size: 24px;
  height: 44px;
  justify-content: center;
  padding: 0;
  width: 44px;
}

.image-lightbox-toolbar button:disabled {
  opacity: 0.38;
}

.image-lightbox-toolbar .zoom-value {
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  width: 58px;
}

.image-lightbox-toolbar .close-button {
  margin-left: 4px;
}

.image-lightbox-stage {
  align-items: center;
  display: flex;
  height: 100%;
  justify-content: center;
  overflow: hidden;
  padding: 72px 58px 50px;
  touch-action: none;
  user-select: none;
  width: 100%;
}

.image-lightbox-stage.zoomed {
  cursor: grab;
}

.image-lightbox-stage.zoomed:active {
  cursor: grabbing;
}

.image-lightbox-stage img {
  display: block;
  max-height: 100%;
  max-width: 100%;
  object-fit: contain;
  transform-origin: center;
  transition: transform 80ms ease-out;
}

.image-lightbox-stage:active img {
  transition: none;
}

.image-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
}

.image-nav.previous {
  left: 10px;
}

.image-nav.next {
  right: 10px;
}

.image-counter {
  bottom: max(12px, env(safe-area-inset-bottom));
  color: rgba(255, 255, 255, 0.82);
  font-size: 13px;
  left: 50%;
  position: absolute;
  transform: translateX(-50%);
  z-index: 3;
}

@media (max-width: 640px) {
  .question-image-gallery,
  .question-image-gallery.single {
    grid-template-columns: 1fr;
  }

  .question-image-thumbnail {
    min-height: 150px;
  }

  .image-lightbox-toolbar {
    left: 0;
    justify-content: center;
    right: 0;
  }

  .image-lightbox-stage {
    padding: 70px 10px 46px;
  }

  .image-nav {
    bottom: max(10px, env(safe-area-inset-bottom));
    top: auto;
    transform: none;
  }

  .image-nav.previous {
    left: 12px;
  }

  .image-nav.next {
    right: 12px;
  }
}
</style>
