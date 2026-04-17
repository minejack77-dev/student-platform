<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Question, Topic } from "@/api.js";
import {
  extractRichTextLines,
  plainTextFromRichText,
  sanitizeInlineRichText,
} from "@/utils/richText.js";

const props = defineProps(["id"]);

const topic = ref({});
const questions = ref([]);
const loadError = ref("");
const saveError = ref("");
const saveSuccess = ref("");
const deleteError = ref("");
const isSaving = ref(false);
const deletingQuestionId = ref(null);
const questionsEditorRef = ref(null);

const bulkForm = ref({
  question_type: "single_choice",
  is_active: true,
  instruction: "",
  shared_choice_one: "",
  shared_choice_two: "",
  questions_html: "",
  keys_raw: "",
});

const resetBulkForm = () => {
  bulkForm.value = {
    question_type: "single_choice",
    is_active: true,
    instruction: "",
    shared_choice_one: "",
    shared_choice_two: "",
    questions_html: "",
    keys_raw: "",
  };
  if (questionsEditorRef.value) {
    questionsEditorRef.value.innerHTML = "";
  }
};

const getNonEmptyLines = (value) =>
  (value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

const enteredQuestionsCount = computed(
  () => extractRichTextLines(bulkForm.value.questions_html).length,
);
const enteredKeysCount = computed(() => getNonEmptyLines(bulkForm.value.keys_raw).length);

const onQuestionsEditorInput = () => {
  bulkForm.value.questions_html = questionsEditorRef.value?.innerHTML || "";
};

const applyQuestionsEditorFormat = (command) => {
  questionsEditorRef.value?.focus();
  if (typeof document !== "undefined") {
    document.execCommand(command, false);
  }
  onQuestionsEditorInput();
};

const getTopic = async () => {
  const response = await Topic.get(props.id);
  topic.value = response;
};

const getQuestions = async () => {
  const response = await Question.filter({ topic: props.id });
  questions.value = response.results ?? response;
};

const loadTopicPage = async () => {
  loadError.value = "";
  try {
    await Promise.all([getTopic(), getQuestions()]);
  } catch {
    loadError.value = "Failed to load topic data.";
  }
};

const parseKeyIndexes = (rawLine) => {
  const tokens = rawLine
    .split(/[\s,;]+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 0);
  if (tokens.length === 0) {
    return { indexes: [], error: "At least one index is required." };
  }

  const indexes = [];
  for (const token of tokens) {
    if (!/^\d+$/.test(token)) {
      return { indexes: [], error: `Invalid key token "${token}". Use numbers only.` };
    }
    indexes.push(Number(token));
  }
  return { indexes: [...new Set(indexes)], error: "" };
};

const buildBulkPayloads = () => {
  const questionLines = extractRichTextLines(bulkForm.value.questions_html);
  const keyLines = getNonEmptyLines(bulkForm.value.keys_raw);
  const sharedChoices = [
    (bulkForm.value.shared_choice_one || "").trim(),
    (bulkForm.value.shared_choice_two || "").trim(),
  ];
  const instruction = (bulkForm.value.instruction || "").trim();

  if (questionLines.length === 0) {
    return { payloads: [], error: "Add at least one question line." };
  }
  if (!sharedChoices[0] || !sharedChoices[1]) {
    return { payloads: [], error: "Fill both shared answer options." };
  }
  if (questionLines.length !== keyLines.length) {
    return {
      payloads: [],
      error: `Questions count (${questionLines.length}) and keys count (${keyLines.length}) must match.`,
    };
  }

  const payloads = [];
  for (let index = 0; index < questionLines.length; index += 1) {
    const questionLineNumber = index + 1;
    const text = questionLines[index];
    const textPlain = plainTextFromRichText(text);

    if (!textPlain) {
      return {
        payloads: [],
        error: `Question line ${questionLineNumber}: question text is required.`,
      };
    }

    const parsedKeys = parseKeyIndexes(keyLines[index]);
    if (parsedKeys.error) {
      return {
        payloads: [],
        error: `Key line ${questionLineNumber}: ${parsedKeys.error}`,
      };
    }

    const outOfRangeIndex = parsedKeys.indexes.find(
      (keyIndex) => keyIndex < 1 || keyIndex > sharedChoices.length,
    );
    if (outOfRangeIndex) {
      return {
        payloads: [],
        error: `Key line ${questionLineNumber}: index ${outOfRangeIndex} is out of range (1..${sharedChoices.length}).`,
      };
    }

    if (bulkForm.value.question_type === "single_choice" && parsedKeys.indexes.length !== 1) {
      return {
        payloads: [],
        error: `Key line ${questionLineNumber}: single choice requires exactly one correct index.`,
      };
    }

    const correctIndexSet = new Set(parsedKeys.indexes);
    const choices = sharedChoices.map((option, optionIndex) => ({
      text: option,
      is_correct: correctIndexSet.has(optionIndex + 1),
      order: optionIndex + 1,
    }));

    payloads.push({
      topic: Number(props.id),
      instruction,
      text,
      question_type: bulkForm.value.question_type,
      is_active: bulkForm.value.is_active,
      choices,
    });
  }

  return { payloads, error: "" };
};

const createQuestions = async () => {
  saveError.value = "";
  saveSuccess.value = "";
  deleteError.value = "";

  const { payloads, error } = buildBulkPayloads();
  if (error) {
    saveError.value = error;
    return;
  }

  isSaving.value = true;
  let createdCount = 0;
  const failedLines = [];
  try {
    for (let index = 0; index < payloads.length; index += 1) {
      try {
        await Question.save(payloads[index]);
        createdCount += 1;
      } catch (requestError) {
        const errorText =
          requestError?.response?.data?.choices?.[0] ||
          requestError?.response?.data?.text?.[0] ||
          requestError?.response?.data?.detail ||
          "Request failed.";
        failedLines.push(`Line ${index + 1}: ${errorText}`);
      }
    }

    if (failedLines.length === 0) {
      saveSuccess.value = `Added ${createdCount} question(s).`;
      resetBulkForm();
    } else {
      const preview = failedLines.slice(0, 3).join(" ");
      const tail =
        failedLines.length > 3 ? ` And ${failedLines.length - 3} more error(s).` : "";
      saveError.value = `Created ${createdCount} of ${payloads.length}. ${preview}${tail}`;
      if (createdCount > 0) {
        saveSuccess.value = `Partially added: ${createdCount} question(s).`;
      }
    }

    await getQuestions();
  } finally {
    isSaving.value = false;
  }
};

const deleteQuestion = async (questionId) => {
  deleteError.value = "";
  saveSuccess.value = "";
  saveError.value = "";
  deletingQuestionId.value = questionId;

  try {
    await Question.delete({ id: questionId });
    questions.value = questions.value.filter((item) => item.id !== questionId);
  } catch (error) {
    deleteError.value = error?.response?.data?.detail || "Could not delete question.";
  } finally {
    deletingQuestionId.value = null;
  }
};

const questionTypeLabel = (value) => {
  if (value === "single_choice") {
    return "Single choice";
  }
  if (value === "multiple_choice") {
    return "Multiple choice";
  }
  return value;
};

const renderRichText = (value) => sanitizeInlineRichText(value || "");

const questionsCount = computed(() => questions.value.length);

watch(
  () => props.id,
  async () => {
    resetBulkForm();
    saveError.value = "";
    saveSuccess.value = "";
    deleteError.value = "";
    await loadTopicPage();
  },
);

onMounted(async () => {
  await loadTopicPage();
});
</script>

<template>
  <div class="topic-page">
    <section class="surface-card topic-hero">
      <div>
        <span class="pill">Topic</span>
        <h1 class="topic-title">{{ topic.title || "Untitled topic" }}</h1>
        <p class="topic-description">{{ topic.description || "No description yet." }}</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <div class="metric-label">Status</div>
          <div class="metric-value">{{ topic.is_active ? "Active" : "Inactive" }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Questions</div>
          <div class="metric-value">{{ questionsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger mt-3">{{ loadError }}</div>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Create Questions</h2>
        <span class="pill">
          {{ bulkForm.question_type === "single_choice" ? "One correct" : "Many correct" }}
        </span>
      </div>

      <div class="row g-3 align-items-end">
        <div class="col-md-7">
          <label class="form-label">Question type</label>
          <select v-model="bulkForm.question_type" class="form-select">
            <option value="single_choice">Single choice</option>
            <option value="multiple_choice">Multiple choice</option>
          </select>
        </div>
        <div class="col-md-5">
          <label class="form-label d-block">Question state</label>
          <div class="form-check mt-2">
            <input id="question-active" v-model="bulkForm.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="question-active">Active</label>
          </div>
        </div>
      </div>

      <div class="mt-3">
        <label class="form-label">Instruction for all added questions</label>
        <textarea
          v-model="bulkForm.instruction"
          class="form-control"
          rows="3"
          placeholder="Example: Read the question and choose the correct option."
        />
      </div>

      <div class="options-grid">
        <div>
          <label class="form-label">Shared option 1</label>
          <input
            v-model="bulkForm.shared_choice_one"
            class="form-control"
            type="text"
            placeholder="First answer option for all questions"
          />
        </div>
        <div>
          <label class="form-label">Shared option 2</label>
          <input
            v-model="bulkForm.shared_choice_two"
            class="form-control"
            type="text"
            placeholder="Second answer option for all questions"
          />
        </div>
      </div>

      <div class="bulk-grid">
        <div>
          <div class="bulk-head">
            <label class="form-label mb-0">Questions list</label>
            <span class="pill">{{ enteredQuestionsCount }} lines</span>
          </div>
          <div class="editor-toolbar">
            <button
              class="editor-btn"
              type="button"
              title="Bold"
              @mousedown.prevent
              @click="applyQuestionsEditorFormat('bold')"
            >
              <strong>B</strong>
            </button>
            <button
              class="editor-btn"
              type="button"
              title="Italic"
              @mousedown.prevent
              @click="applyQuestionsEditorFormat('italic')"
            >
              <em>I</em>
            </button>
            <button
              class="editor-btn"
              type="button"
              title="Underline"
              @mousedown.prevent
              @click="applyQuestionsEditorFormat('underline')"
            >
              <u>U</u>
            </button>
            <button
              class="editor-btn"
              type="button"
              title="Clear formatting"
              @mousedown.prevent
              @click="applyQuestionsEditorFormat('removeFormat')"
            >
              Clear
            </button>
          </div>
          <div
            ref="questionsEditorRef"
            class="rich-editor"
            contenteditable="true"
            data-placeholder="Question text line 1&#10;Question text line 2&#10;Question text line 3"
            @input="onQuestionsEditorInput"
          />
          <p class="field-hint">
            One question per line. Use Enter for next question. Formatting (bold, italic, underline) is saved.
          </p>
        </div>

        <div>
          <div class="bulk-head">
            <label class="form-label mb-0">Answer keys</label>
            <span class="pill">{{ enteredKeysCount }} lines</span>
          </div>
          <textarea
            v-model="bulkForm.keys_raw"
            class="form-control bulk-textarea"
            rows="10"
            placeholder="2&#10;1&#10;1,2"
          />
          <p class="field-hint">
            One key line per question. Use option numbers (1-based). With two options use <code>1</code>, <code>2</code> or <code>1,2</code>.
          </p>
        </div>
      </div>

      <div v-if="saveError" class="alert alert-danger mt-3">{{ saveError }}</div>
      <div v-if="saveSuccess" class="alert alert-success mt-3">{{ saveSuccess }}</div>

      <div class="panel-actions">
        <button class="btn btn-primary" :disabled="isSaving" type="button" @click="createQuestions">
          {{ isSaving ? "Saving..." : "Add questions" }}
        </button>
      </div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Questions in Topic</h2>
        <span class="pill">{{ questionsCount }} total</span>
      </div>

      <div v-if="deleteError" class="alert alert-danger mb-3">{{ deleteError }}</div>

      <div v-if="questions.length === 0" class="empty-box">No questions yet.</div>

      <article
        v-for="(question, index) in questions"
        :key="question.id"
        class="question-item"
        :style="{ '--delay': `${index * 45}ms` }"
      >
        <div class="question-head">
          <div>
            <div class="question-text" v-html="renderRichText(question.text)" />
            <div v-if="question.instruction" class="question-instruction">
              Instruction: {{ question.instruction }}
            </div>
          </div>
          <div class="question-actions">
            <span class="question-type">{{ questionTypeLabel(question.question_type) }}</span>
            <button
              class="ghost-danger-btn"
              type="button"
              :disabled="deletingQuestionId === question.id"
              @click="deleteQuestion(question.id)"
            >
              {{ deletingQuestionId === question.id ? "Removing..." : "Delete" }}
            </button>
          </div>
        </div>

        <ul class="choice-list">
          <li v-for="choice in question.choices" :key="choice.id" :class="{ 'choice-correct-text': choice.is_correct }">
            {{ choice.text }}
            <span v-if="choice.is_correct"> (correct)</span>
          </li>
        </ul>
      </article>
    </section>
  </div>
</template>

<style scoped src="./TopicDetail.css"></style>
