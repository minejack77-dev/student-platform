<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Question, Topic } from "@/api.js";

const props = defineProps(["id"]);

const topic = ref({});
const questions = ref([]);
const loadError = ref("");
const saveError = ref("");
const saveSuccess = ref("");
const deleteError = ref("");
const isSaving = ref(false);
const deletingQuestionId = ref(null);

const questionForm = ref({
  text: "",
  question_type: "multiple_choice",
  is_active: true,
  choices: [
    { text: "", is_correct: false, order: 1 },
    { text: "", is_correct: false, order: 2 },
  ],
});

const normalizeOrders = () => {
  questionForm.value.choices = questionForm.value.choices.map((choice, index) => ({
    ...choice,
    order: index + 1,
  }));
};

const resetForm = () => {
  questionForm.value = {
    text: "",
    question_type: "multiple_choice",
    is_active: true,
    choices: [
      { text: "", is_correct: false, order: 1 },
      { text: "", is_correct: false, order: 2 },
    ],
  };
};

const addChoice = () => {
  questionForm.value.choices.push({
    text: "",
    is_correct: false,
    order: questionForm.value.choices.length + 1,
  });
};

const removeChoice = (index) => {
  if (questionForm.value.choices.length <= 2) {
    return;
  }
  questionForm.value.choices.splice(index, 1);
  normalizeOrders();
};

const setSingleCorrect = (index) => {
  questionForm.value.choices = questionForm.value.choices.map((choice, choiceIndex) => ({
    ...choice,
    is_correct: choiceIndex === index,
  }));
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

const buildPayloadChoices = () =>
  questionForm.value.choices
    .map((choice, index) => ({
      text: (choice.text || "").trim(),
      is_correct: !!choice.is_correct,
      order: index + 1,
    }))
    .filter((choice) => choice.text.length > 0);

const validateForm = (choices) => {
  if (!questionForm.value.text.trim()) {
    return "Question text is required.";
  }
  if (choices.length < 2) {
    return "At least two non-empty answer choices are required.";
  }
  const correctCount = choices.filter((choice) => choice.is_correct).length;
  if (questionForm.value.question_type === "single_choice" && correctCount !== 1) {
    return "Single choice question must have exactly one correct answer.";
  }
  if (questionForm.value.question_type === "multiple_choice" && correctCount < 1) {
    return "Multiple choice question must have at least one correct answer.";
  }
  return "";
};

const createQuestion = async () => {
  saveError.value = "";
  saveSuccess.value = "";
  deleteError.value = "";

  const choices = buildPayloadChoices();
  const validationMessage = validateForm(choices);
  if (validationMessage) {
    saveError.value = validationMessage;
    return;
  }

  isSaving.value = true;
  try {
    await Question.save({
      topic: Number(props.id),
      text: questionForm.value.text.trim(),
      question_type: questionForm.value.question_type,
      is_active: questionForm.value.is_active,
      choices,
    });
    saveSuccess.value = "Question created.";
    resetForm();
    await getQuestions();
  } catch (error) {
    saveError.value =
      error?.response?.data?.detail ||
      "Could not create question. Check question type and answers.";
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
    deleteError.value =
      error?.response?.data?.detail || "Could not delete question.";
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

const questionsCount = computed(() => questions.value.length);

watch(
  () => props.id,
  async () => {
    resetForm();
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
        <h2 class="section-title">Create Question</h2>
        <span class="pill">
          {{ questionForm.question_type === "single_choice" ? "One correct" : "Many correct" }}
        </span>
      </div>

      <div class="mb-3">
        <label class="form-label">Question text</label>
        <textarea
          v-model="questionForm.text"
          class="form-control"
          rows="3"
          placeholder="Type your question here"
        />
      </div>

      <div class="row g-3 align-items-end">
        <div class="col-md-7">
          <label class="form-label">Question type</label>
          <select v-model="questionForm.question_type" class="form-select">
            <option value="single_choice">Single choice</option>
            <option value="multiple_choice">Multiple choice</option>
          </select>
        </div>
        <div class="col-md-5">
          <label class="form-label d-block">Question state</label>
          <div class="form-check mt-2">
            <input id="question-active" v-model="questionForm.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="question-active">Active</label>
          </div>
        </div>
      </div>

      <div class="choices-wrap">
        <div class="choices-head">
          <h3 class="choices-title">Answer choices</h3>
          <button class="btn btn-outline-primary btn-sm" type="button" @click="addChoice">Add choice</button>
        </div>

        <div v-for="(choice, index) in questionForm.choices" :key="index" class="choice-row">
          <div class="choice-toggle">
            <input
              v-if="questionForm.question_type === 'single_choice'"
              :checked="choice.is_correct"
              class="form-check-input"
              name="single-correct"
              type="radio"
              @change="setSingleCorrect(index)"
            />
            <input v-else v-model="choice.is_correct" class="form-check-input" type="checkbox" />
          </div>

          <input v-model="choice.text" class="form-control" type="text" :placeholder="`Choice #${index + 1}`" />

          <button
            class="btn btn-outline-danger btn-sm"
            type="button"
            :disabled="questionForm.choices.length <= 2"
            @click="removeChoice(index)"
          >
            Remove
          </button>
        </div>
      </div>

      <div v-if="saveError" class="alert alert-danger mt-3">{{ saveError }}</div>
      <div v-if="saveSuccess" class="alert alert-success mt-3">{{ saveSuccess }}</div>

      <div class="panel-actions">
        <button class="btn btn-primary" :disabled="isSaving" type="button" @click="createQuestion">
          {{ isSaving ? "Saving..." : "Create question" }}
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
          <div class="question-text">{{ question.text }}</div>
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

<style scoped>
.topic-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.topic-hero {
  align-items: end;
  animation: rise-fade 420ms ease both;
  background:
    radial-gradient(circle at 85% 25%, rgba(12, 169, 146, 0.2), transparent 42%),
    linear-gradient(120deg, rgba(255, 255, 255, 0.9) 0%, rgba(240, 249, 255, 0.9) 100%);
  display: grid;
  gap: 14px;
  grid-template-columns: 1.15fr 0.85fr;
  padding: 24px;
}

.topic-title {
  font-size: clamp(28px, 3.8vw, 38px);
  margin: 10px 0 6px;
}

.topic-description {
  color: var(--ink-soft);
  margin: 0;
  max-width: 640px;
}

.hero-metrics {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
}

.metric-card {
  background: var(--surface-strong);
  border: 1px solid rgba(20, 46, 72, 0.12);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2);
  padding: 12px;
}

.metric-label {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.metric-value {
  font-family: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  font-size: 24px;
  font-weight: 700;
}

.panel-card {
  animation: rise-fade 420ms ease both;
  padding: 20px;
}

.panel-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title {
  font-size: 27px;
  margin: 0;
}

.choices-wrap {
  margin-top: 18px;
}

.choices-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.choices-title {
  font-size: 18px;
  margin: 0;
}

.choice-row {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 34px 1fr auto;
  margin-bottom: 10px;
}

.choice-toggle {
  align-items: center;
  display: flex;
  justify-content: center;
}

.panel-actions {
  margin-top: 14px;
}

.empty-box {
  border: 1px dashed rgba(20, 45, 72, 0.24);
  border-radius: var(--radius-md);
  color: var(--ink-soft);
  padding: 14px;
}

.question-item {
  animation: rise-fade 350ms ease both;
  animation-delay: var(--delay);
  background: var(--surface-strong);
  border: 1px solid rgba(16, 39, 64, 0.12);
  border-radius: var(--radius-lg);
  margin-bottom: 12px;
  padding: 14px;
}

.question-head {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.question-text {
  font-size: 17px;
  font-weight: 700;
}

.question-type {
  background: rgba(31, 95, 216, 0.12);
  border-radius: 999px;
  color: var(--brand-blue-strong);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
  white-space: nowrap;
}

.question-actions {
  align-items: center;
  display: flex;
  gap: 8px;
}

.ghost-danger-btn {
  background: rgba(193, 61, 61, 0.14);
  border: 1px solid rgba(193, 61, 61, 0.26);
  border-radius: 999px;
  color: #9d2727;
  font-size: 12px;
  font-weight: 700;
  padding: 5px 10px;
  transition: background 120ms ease;
}

.ghost-danger-btn:hover:not(:disabled) {
  background: rgba(193, 61, 61, 0.2);
}

.ghost-danger-btn:disabled {
  opacity: 0.6;
}

.choice-list {
  margin: 10px 0 0;
}

.choice-correct-text {
  color: var(--success);
  font-weight: 700;
}

@media (max-width: 900px) {
  .topic-hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .choice-row {
    grid-template-columns: 34px 1fr;
  }

  .panel-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .hero-metrics {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
