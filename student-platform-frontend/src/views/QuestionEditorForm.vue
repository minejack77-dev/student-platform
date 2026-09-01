<script setup>
import { useI18n } from "vue-i18n";

defineProps({
  form: {
    type: Object,
    required: true,
  },
  questionTypes: {
    type: Array,
    required: true,
  },
  isMatching: {
    type: Boolean,
    required: true,
  },
  isSingleChoice: {
    type: Boolean,
    required: true,
  },
  isSaving: {
    type: Boolean,
    default: false,
  },
  canSave: {
    type: Boolean,
    default: true,
  },
  error: {
    type: String,
    default: "",
  },
  success: {
    type: String,
    default: "",
  },
  saveLabel: {
    type: String,
    required: true,
  },
});

const emit = defineEmits([
  "question-type-change",
  "add-choice",
  "remove-choice",
  "set-choice-correct",
  "add-matching-pair",
  "remove-matching-pair",
  "save",
  "cancel",
]);

const { t } = useI18n();
</script>

<template>
  <div class="question-editor">
    <div class="editor-grid">
      <label>
        <span class="form-label">{{ t("topicDetail.questionType") }}</span>
        <select
          v-model="form.question_type"
          class="form-select"
          :disabled="isSaving"
          @change="emit('question-type-change')"
        >
          <option v-for="type in questionTypes" :key="type.value" :value="type.value">
            {{ type.label }}
          </option>
        </select>
      </label>
    </div>

    <div>
      <label class="form-label">{{ t("common.question") }}</label>
      <textarea
        v-model="form.text"
        class="form-control"
        rows="3"
        :placeholder="t('topicDetail.questionTextPlaceholder')"
      />
    </div>

    <div>
      <label class="form-label">{{ t("topicDetail.instruction") }}</label>
      <textarea
        v-model="form.instruction"
        class="form-control"
        rows="2"
        :placeholder="t('common.optional')"
      />
    </div>

    <div v-if="!isMatching" class="answer-editor">
      <div class="answer-editor-head">
        <h3 class="task-subsection-title">{{ t("topicDetail.answerOptions") }}</h3>
        <button class="btn btn-outline-primary btn-sm" type="button" @click="emit('add-choice')">
          {{ t("topicDetail.addOption") }}
        </button>
      </div>

      <div class="choice-editor-list">
        <div
          v-for="(choice, index) in form.choices"
          :key="index"
          class="choice-editor-row"
        >
          <input
            :type="isSingleChoice ? 'radio' : 'checkbox'"
            :name="`correct-choice-${form.id || 'new'}`"
            :checked="choice.is_correct"
            class="form-check-input"
            @change="emit('set-choice-correct', index, $event.target.checked)"
          />
          <textarea
            v-model="choice.text"
            class="form-control"
            rows="1"
            :placeholder="t('topicDetail.optionPlaceholder', { number: index + 1 })"
          />
          <button
            class="ghost-danger-btn"
            type="button"
            :disabled="form.choices.length <= 2"
            @click="emit('remove-choice', index)"
          >
            {{ t("common.remove") }}
          </button>
        </div>
      </div>
    </div>

    <div v-else class="answer-editor">
      <div class="answer-editor-head">
        <h3 class="task-subsection-title">{{ t("topicDetail.matchingPairs") }}</h3>
        <button class="btn btn-outline-primary btn-sm" type="button" @click="emit('add-matching-pair')">
          {{ t("topicDetail.addPair") }}
        </button>
      </div>

      <div class="matching-editor-head">
        <span>{{ t("topicDetail.leftColumn") }}</span>
        <span>{{ t("topicDetail.rightColumn") }}</span>
      </div>
      <div class="matching-editor-list">
        <div
          v-for="(pair, index) in form.matching_pairs"
          :key="index"
          class="matching-editor-row"
        >
          <textarea
            v-model="pair.left_content"
            class="form-control"
            rows="2"
            :placeholder="t('topicDetail.leftPlaceholder', { number: index + 1 })"
          />
          <textarea
            v-model="pair.right_content"
            class="form-control"
            rows="2"
            :placeholder="t('topicDetail.rightPlaceholder', { number: index + 1 })"
          />
          <button
            class="ghost-danger-btn"
            type="button"
            :disabled="form.matching_pairs.length <= 2"
            @click="emit('remove-matching-pair', index)"
          >
            {{ t("common.remove") }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="success" class="alert alert-success">{{ success }}</div>

    <div class="editor-actions">
      <button
        class="btn btn-primary"
        type="button"
        :disabled="isSaving || !canSave"
        @click="emit('save')"
      >
        {{ saveLabel }}
      </button>
      <button class="btn btn-outline-secondary" type="button" @click="emit('cancel')">
        {{ t("common.cancel") }}
      </button>
    </div>
  </div>
</template>

<style scoped src="./QuestionEditorForm.css"></style>
