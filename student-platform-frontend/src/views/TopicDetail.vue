<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { Question, Task, Topic } from "@/api.js";
import { sanitizeInlineRichText } from "@/utils/richText.js";
import QuestionEditorForm from "./QuestionEditorForm.vue";

const props = defineProps(["id"]);
const { t } = useI18n();

const topic = ref({});
const tasks = ref([]);
const selectedTaskId = ref("");
const questions = ref([]);
const loadError = ref("");
const importError = ref("");
const importSuccess = ref("");
const deleteError = ref("");
const isImporting = ref(false);
const deletingQuestionId = ref(null);
const questionFile = ref(null);
const fileInputRef = ref(null);
const importForm = ref({
  question_type: "single_choice",
});
const questionForm = ref(createBlankQuestionForm());
const questionFormError = ref("");
const questionFormSuccess = ref("");
const isQuestionSaving = ref(false);
const openQuestionEditorId = ref(null);
const taskForm = ref({
  title: "",
  description: "",
  questions_per_attempt: 10,
  passing_correct_answers: 8,
  is_active: true,
});
const currentTaskForm = ref({
  questions_per_attempt: 10,
  passing_correct_answers: 8,
});
const taskSaveError = ref("");
const taskSaveSuccess = ref("");
const isTaskSaving = ref(false);
const currentTaskSaveError = ref("");
const currentTaskSaveSuccess = ref("");
const isCurrentTaskSaving = ref(false);

function createBlankQuestionForm() {
  return {
    id: null,
    question_type: "single_choice",
    text: "",
    instruction: "",
    is_active: true,
    choices: [
      { id: null, text: "", is_correct: true, order: 1 },
      { id: null, text: "", is_correct: false, order: 2 },
    ],
    matching_pairs: [
      { id: null, left_content: "", right_content: "", order: 1 },
      { id: null, left_content: "", right_content: "", order: 2 },
    ],
  };
}

const questionTypes = computed(() => [
  { value: "single_choice", label: t("topicDetail.singleChoice") },
  { value: "multiple_choice", label: t("topicDetail.multipleChoice") },
  { value: "matching", label: t("topicDetail.matching") },
]);

const getApiErrorMessage = (data) => {
  if (!data) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }

  const fields = [
    "detail",
    "src",
    "task",
    "topic",
    "question_type",
    "text",
    "instruction",
    "choices",
    "matching_pairs",
    "questions_per_attempt",
    "passing_correct_answers",
    "non_field_errors",
  ];
  for (const field of fields) {
    const value = data[field];
    if (Array.isArray(value) && value.length > 0) {
      return value[0];
    }
    if (typeof value === "string") {
      return value;
    }
  }
  return "";
};

const validateAttemptSettings = (form) => {
  const questionsPerAttempt = Number(form.questions_per_attempt);
  const passingCorrectAnswers = Number(form.passing_correct_answers);
  if (!Number.isInteger(questionsPerAttempt) || questionsPerAttempt < 1) {
    return { error: t("topicDetail.errors.questionCountMin") };
  }
  if (!Number.isInteger(passingCorrectAnswers) || passingCorrectAnswers < 1) {
    return { error: t("topicDetail.errors.passingMin") };
  }
  if (passingCorrectAnswers > questionsPerAttempt) {
    return { error: t("topicDetail.errors.passingExceeds") };
  }
  return { questionsPerAttempt, passingCorrectAnswers };
};

const resetImportForm = () => {
  questionFile.value = null;
  importForm.value = { question_type: "single_choice" };
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
};

const resetQuestionForm = () => {
  questionForm.value = createBlankQuestionForm();
  questionFormError.value = "";
  questionFormSuccess.value = "";
  openQuestionEditorId.value = null;
};

const getTopic = async () => {
  const response = await Topic.get(props.id);
  topic.value = response;
};

const getTasks = async () => {
  const response = await Task.filter({ topic: props.id, ordering: "title" });
  tasks.value = response.results ?? response;
  if (!selectedTaskId.value && tasks.value.length > 0) {
    selectedTaskId.value = String(tasks.value[0].id);
  }
};

const getQuestions = async () => {
  if (!selectedTaskId.value) {
    questions.value = [];
    return;
  }
  const response = await Question.filter({
    task: selectedTaskId.value,
    page_size: 200,
  });
  questions.value = response.results ?? response;
};

const loadTopicPage = async () => {
  loadError.value = "";
  try {
    await Promise.all([getTopic(), getTasks()]);
    await getQuestions();
  } catch {
    loadError.value = t("topicDetail.loadError");
  }
};

const createTask = async () => {
  taskSaveError.value = "";
  taskSaveSuccess.value = "";
  const title = taskForm.value.title.trim();
  if (!title) {
    taskSaveError.value = t("topicDetail.errors.taskTitleRequired");
    return;
  }
  const settings = validateAttemptSettings(taskForm.value);
  if (settings.error) {
    taskSaveError.value = settings.error;
    return;
  }

  isTaskSaving.value = true;
  try {
    const createdTask = await Task.save({
      topic: Number(props.id),
      title,
      description: taskForm.value.description.trim(),
      questions_per_attempt: settings.questionsPerAttempt,
      passing_correct_answers: settings.passingCorrectAnswers,
      is_active: taskForm.value.is_active,
    });
    taskForm.value = {
      title: "",
      description: "",
      questions_per_attempt: 10,
      passing_correct_answers: 8,
      is_active: true,
    };
    selectedTaskId.value = String(createdTask.id);
    taskSaveSuccess.value = t("topicDetail.taskCreated");
    await getTasks();
    await getQuestions();
  } catch (error) {
    taskSaveError.value =
      error?.response?.data?.title?.[0] ||
      getApiErrorMessage(error?.response?.data) ||
      error?.response?.data?.detail ||
      t("topicDetail.errors.createTask");
  } finally {
    isTaskSaving.value = false;
  }
};

const updateCurrentTaskSettings = async () => {
  currentTaskSaveError.value = "";
  currentTaskSaveSuccess.value = "";
  if (!selectedTask.value) {
    currentTaskSaveError.value = t("topicDetail.errors.selectTask");
    return;
  }

  const settings = validateAttemptSettings(currentTaskForm.value);
  if (settings.error) {
    currentTaskSaveError.value = settings.error;
    return;
  }

  isCurrentTaskSaving.value = true;
  try {
    const updatedTask = await Task.save({
      id: selectedTask.value.id,
      questions_per_attempt: settings.questionsPerAttempt,
      passing_correct_answers: settings.passingCorrectAnswers,
    });
    tasks.value = tasks.value.map((task) =>
      task.id === updatedTask.id ? updatedTask : task,
    );
    currentTaskSaveSuccess.value = t("topicDetail.taskSettingsSaved");
  } catch (error) {
    currentTaskSaveError.value =
      getApiErrorMessage(error?.response?.data) || t("topicDetail.errors.saveSettings");
  } finally {
    isCurrentTaskSaving.value = false;
  }
};

const isMatchingForm = computed(() => questionForm.value.question_type === "matching");
const isSingleChoiceForm = computed(
  () => questionForm.value.question_type === "single_choice",
);

const addChoice = () => {
  questionForm.value.choices.push({
    id: null,
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
  questionForm.value.choices = questionForm.value.choices.map((choice, choiceIndex) => ({
    ...choice,
    order: choiceIndex + 1,
  }));
  if (
    isSingleChoiceForm.value &&
    !questionForm.value.choices.some((choice) => choice.is_correct)
  ) {
    questionForm.value.choices[0].is_correct = true;
  }
};

const setChoiceCorrect = (index, checked) => {
  if (isSingleChoiceForm.value) {
    questionForm.value.choices = questionForm.value.choices.map((choice, choiceIndex) => ({
      ...choice,
      is_correct: choiceIndex === index,
    }));
    return;
  }
  questionForm.value.choices[index].is_correct = checked;
};

const addMatchingPair = () => {
  questionForm.value.matching_pairs.push({
    id: null,
    left_content: "",
    right_content: "",
    order: questionForm.value.matching_pairs.length + 1,
  });
};

const removeMatchingPair = (index) => {
  if (questionForm.value.matching_pairs.length <= 2) {
    return;
  }
  questionForm.value.matching_pairs.splice(index, 1);
  questionForm.value.matching_pairs = questionForm.value.matching_pairs.map(
    (pair, pairIndex) => ({
      ...pair,
      order: pairIndex + 1,
    }),
  );
};

const onQuestionTypeChange = () => {
  questionFormError.value = "";
  questionFormSuccess.value = "";
  if (isSingleChoiceForm.value) {
    const firstCorrectIndex = questionForm.value.choices.findIndex(
      (choice) => choice.is_correct,
    );
    questionForm.value.choices = questionForm.value.choices.map((choice, index) => ({
      ...choice,
      is_correct: index === Math.max(firstCorrectIndex, 0),
    }));
  }
};

const startNewQuestion = () => {
  questionForm.value = createBlankQuestionForm();
  questionFormError.value = "";
  questionFormSuccess.value = "";
  deleteError.value = "";
  importError.value = "";
  importSuccess.value = "";
  openQuestionEditorId.value = "new";
};

const editQuestion = (question) => {
  questionFormError.value = "";
  questionFormSuccess.value = "";
  deleteError.value = "";
  importError.value = "";
  importSuccess.value = "";
  questionForm.value = {
    id: question.id,
    question_type: question.question_type,
    text: question.text || "",
    instruction: question.instruction || "",
    is_active: true,
    choices:
      question.choices?.length > 0
        ? question.choices.map((choice, index) => ({
            id: choice.id,
            text: choice.text || "",
            is_correct: Boolean(choice.is_correct),
            order: choice.order || index + 1,
          }))
        : createBlankQuestionForm().choices,
    matching_pairs:
      question.matching_pairs?.length > 0
        ? question.matching_pairs.map((pair, index) => ({
            id: pair.id,
            left_content: pair.left_content || "",
            right_content: pair.right_content || "",
            order: pair.order || index + 1,
          }))
        : createBlankQuestionForm().matching_pairs,
  };
  openQuestionEditorId.value = question.id;
};

const validateQuestionForm = () => {
  if (!selectedTaskId.value) {
    return t("topicDetail.errors.createOrSelectTask");
  }
  if (!questionForm.value.text.trim()) {
    return t("topicDetail.errors.questionTextRequired");
  }

  if (isMatchingForm.value) {
    const pairs = questionForm.value.matching_pairs.filter(
      (pair) => pair.left_content.trim() || pair.right_content.trim(),
    );
    if (pairs.length < 2) {
      return t("topicDetail.errors.matchingPairsMin");
    }
    if (pairs.some((pair) => !pair.left_content.trim() || !pair.right_content.trim())) {
      return t("topicDetail.errors.matchingPairsComplete");
    }
    return "";
  }

  const choices = questionForm.value.choices.filter((choice) => choice.text.trim());
  if (choices.length < 2) {
    return t("topicDetail.errors.choicesMin");
  }
  const correctCount = choices.filter((choice) => choice.is_correct).length;
  if (isSingleChoiceForm.value && correctCount !== 1) {
    return t("topicDetail.errors.singleCorrectRequired");
  }
  if (!isSingleChoiceForm.value && correctCount < 1) {
    return t("topicDetail.errors.multipleCorrectRequired");
  }
  return "";
};

const saveQuestion = async () => {
  questionFormError.value = "";
  questionFormSuccess.value = "";
  deleteError.value = "";
  importError.value = "";
  importSuccess.value = "";

  const validationError = validateQuestionForm();
  if (validationError) {
    questionFormError.value = validationError;
    return;
  }

  const payload = {
    topic: Number(props.id),
    task: Number(selectedTaskId.value),
    instruction: questionForm.value.instruction.trim(),
    text: questionForm.value.text.trim(),
    question_type: questionForm.value.question_type,
    is_active: true,
  };
  if (questionForm.value.id) {
    payload.id = questionForm.value.id;
  }

  if (isMatchingForm.value) {
    payload.choices = [];
    payload.matching_pairs = questionForm.value.matching_pairs
      .filter((pair) => pair.left_content.trim() || pair.right_content.trim())
      .map((pair, index) => ({
        left_content: pair.left_content.trim(),
        right_content: pair.right_content.trim(),
        order: index + 1,
      }));
  } else {
    payload.matching_pairs = [];
    payload.choices = questionForm.value.choices
      .filter((choice) => choice.text.trim())
      .map((choice, index) => ({
        text: choice.text.trim(),
        is_correct: Boolean(choice.is_correct),
        order: index + 1,
      }));
  }

  isQuestionSaving.value = true;
  try {
    await Question.save(payload);
    const successMessage = questionForm.value.id
      ? t("topicDetail.questionUpdated")
      : t("topicDetail.questionCreated");
    resetQuestionForm();
    questionFormSuccess.value = successMessage;
    await getQuestions();
  } catch (error) {
    questionFormError.value =
      getApiErrorMessage(error?.response?.data) ||
      t("topicDetail.errors.saveQuestion");
  } finally {
    isQuestionSaving.value = false;
  }
};

const onQuestionFileChange = (event) => {
  importError.value = "";
  importSuccess.value = "";
  questionFile.value = event.target.files?.[0] ?? null;
};

const importQuestions = async () => {
  importError.value = "";
  importSuccess.value = "";
  deleteError.value = "";

  if (!selectedTaskId.value) {
    importError.value = t("topicDetail.errors.createOrSelectTask");
    return;
  }
  if (!questionFile.value) {
    importError.value = t("topicDetail.errors.chooseFile");
    return;
  }

  const formData = new FormData();
  formData.append("src", questionFile.value);
  formData.append("question_type", importForm.value.question_type);

  isImporting.value = true;
  try {
    const response = await Task.importQuestions(selectedTaskId.value, formData);
    importSuccess.value = t("topicDetail.messages.importedQuestions", {
      count: response.imported_count,
    });
    resetImportForm();
    await Promise.all([getTasks(), getQuestions()]);
  } catch (error) {
    importError.value =
      getApiErrorMessage(error?.response?.data) || t("topicDetail.errors.importQuestions");
  } finally {
    isImporting.value = false;
  }
};

const deleteQuestion = async (questionId) => {
  deleteError.value = "";
  importSuccess.value = "";
  importError.value = "";
  deletingQuestionId.value = questionId;

  try {
    await Question.delete({ id: questionId });
    if (openQuestionEditorId.value === questionId) {
      resetQuestionForm();
    }
    questions.value = questions.value.filter((item) => item.id !== questionId);
  } catch (error) {
    deleteError.value = error?.response?.data?.detail || t("topicDetail.errors.deleteQuestion");
  } finally {
    deletingQuestionId.value = null;
  }
};

const questionTypeLabel = (value) => {
  if (value === "single_choice") {
    return t("topicDetail.singleChoice");
  }
  if (value === "multiple_choice") {
    return t("topicDetail.multipleChoice");
  }
  if (value === "matching") {
    return t("topicDetail.matching");
  }
  return value;
};

const renderRichText = (value) => sanitizeInlineRichText(value || "");

const questionsCount = computed(() => questions.value.length);
const tasksCount = computed(() => tasks.value.length);
const selectedTask = computed(() =>
  tasks.value.find((task) => String(task.id) === String(selectedTaskId.value)),
);
const selectedFileName = computed(() => questionFile.value?.name || t("common.noFileSelected"));

watch(
  () => props.id,
  async () => {
    selectedTaskId.value = "";
    importError.value = "";
    importSuccess.value = "";
    deleteError.value = "";
    resetImportForm();
    await loadTopicPage();
  },
);

onMounted(async () => {
  await loadTopicPage();
});

watch(selectedTaskId, async () => {
  importError.value = "";
  importSuccess.value = "";
  deleteError.value = "";
  currentTaskSaveError.value = "";
  currentTaskSaveSuccess.value = "";
  resetQuestionForm();
  resetImportForm();
  await getQuestions();
});

watch(
  selectedTask,
  (task) => {
    if (!task) {
      currentTaskForm.value = {
        questions_per_attempt: 10,
        passing_correct_answers: 8,
      };
      return;
    }
    currentTaskForm.value = {
      questions_per_attempt: task.questions_per_attempt ?? 10,
      passing_correct_answers: task.passing_correct_answers ?? 8,
    };
  },
  { immediate: true },
);
</script>

<template>
  <div class="topic-page">
    <section class="surface-card topic-hero">
      <div>
        <span class="pill">{{ t("topicDetail.badge") }}</span>
        <h1 class="topic-title">{{ topic.title || t("common.untitledLesson") }}</h1>
        <p class="topic-description">{{ topic.description || t("common.noDescriptionYet") }}</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <div class="metric-label">{{ t("common.status") }}</div>
          <div class="metric-value">{{ topic.is_active ? t("common.active") : t("common.inactive") }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ t("common.tasks") }}</div>
          <div class="metric-value">{{ tasksCount }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ t("topicDetail.selectedQuestions") }}</div>
          <div class="metric-value">{{ questionsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger mt-3">{{ loadError }}</div>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t("topicDetail.tasksInLesson") }}</h2>
        <span class="pill">{{ t("common.totalCount", { count: tasksCount }) }}</span>
      </div>

      <div class="task-sections">
        <div class="task-subsection current-task-section">
          <h3 class="task-subsection-title">{{ t("topicDetail.currentTask") }}</h3>

          <div class="task-settings-grid">
            <div>
              <label class="form-label">{{ t("common.task") }}</label>
              <select v-model="selectedTaskId" class="form-select">
                <option value="">{{ t("topicDetail.noTaskSelected") }}</option>
                <option v-for="taskItem in tasks" :key="taskItem.id" :value="String(taskItem.id)">
                  {{ taskItem.title }}
                </option>
              </select>
            </div>

            <div>
              <label class="form-label">{{ t("common.questions") }}</label>
              <input
                v-model.number="currentTaskForm.questions_per_attempt"
                class="form-control"
                :disabled="!selectedTask"
                min="1"
                step="1"
                type="number"
              />
            </div>

            <div>
              <label class="form-label">{{ t("topicDetail.passFrom") }}</label>
              <input
                v-model.number="currentTaskForm.passing_correct_answers"
                class="form-control"
                :disabled="!selectedTask"
                min="1"
                :max="currentTaskForm.questions_per_attempt"
                step="1"
                type="number"
              />
            </div>

            <button
              class="btn btn-outline-primary task-settings-btn"
              type="button"
              :disabled="!selectedTask || isCurrentTaskSaving"
              @click="updateCurrentTaskSettings"
            >
              {{ isCurrentTaskSaving ? t("common.saving") : t("topicDetail.saveSettings") }}
            </button>
          </div>

          <div v-if="selectedTask" class="field-hint mt-3">
            {{ t("topicDetail.selectedPool", { title: selectedTask.title }) }}
          </div>
          <div v-if="currentTaskSaveError" class="alert alert-danger mt-3">{{ currentTaskSaveError }}</div>
          <div v-if="currentTaskSaveSuccess" class="alert alert-success mt-3">{{ currentTaskSaveSuccess }}</div>
        </div>

        <div class="task-subsection">
          <h3 class="task-subsection-title">{{ t("topicDetail.newTask") }}</h3>

          <div class="new-task-grid">
            <div>
              <label class="form-label">{{ t("common.title") }}</label>
              <input
                v-model="taskForm.title"
                class="form-control"
                type="text"
                :placeholder="t('topicDetail.taskTitlePlaceholder')"
              />
            </div>

            <div>
              <label class="form-label">{{ t("common.description") }}</label>
              <input
                v-model="taskForm.description"
                class="form-control"
                type="text"
                :placeholder="t('common.optional')"
              />
            </div>

            <div>
              <label class="form-label">{{ t("common.questions") }}</label>
              <input
                v-model.number="taskForm.questions_per_attempt"
                class="form-control"
                min="1"
                step="1"
                type="number"
              />
            </div>

            <div>
              <label class="form-label">{{ t("topicDetail.passFrom") }}</label>
              <input
                v-model.number="taskForm.passing_correct_answers"
                class="form-control"
                min="1"
                :max="taskForm.questions_per_attempt"
                step="1"
                type="number"
              />
            </div>

            <button class="btn btn-primary new-task-btn" type="button" :disabled="isTaskSaving" @click="createTask">
              {{ isTaskSaving ? t("common.creating") : t("topicDetail.createTask") }}
            </button>
          </div>

          <div class="form-check mt-3">
            <input id="task-active" v-model="taskForm.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="task-active">{{ t("common.active") }}</label>
          </div>

          <div v-if="taskSaveError" class="alert alert-danger mt-3">{{ taskSaveError }}</div>
          <div v-if="taskSaveSuccess" class="alert alert-success mt-3">{{ taskSaveSuccess }}</div>
        </div>
      </div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t("topicDetail.importQuestions") }}</h2>
        <span class="pill">.xls / .xlsx</span>
      </div>

      <div class="import-grid">
        <div>
          <label class="form-label">{{ t("topicDetail.questionType") }}</label>
          <select v-model="importForm.question_type" class="form-select">
            <option v-for="type in questionTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="form-label">{{ t("topicDetail.questionFile") }}</label>
          <label class="file-drop">
            <input
              ref="fileInputRef"
              type="file"
              accept=".xls,.xlsx"
              class="file-input"
              @change="onQuestionFileChange"
            />
            <span class="file-name">{{ selectedFileName }}</span>
            <span class="file-action">{{ t("common.chooseFile") }}</span>
          </label>
        </div>

        <button
          class="btn btn-primary import-btn"
          type="button"
          :disabled="isImporting || !selectedTaskId"
          @click="importQuestions"
        >
          {{ isImporting ? t("topicDetail.importing") : t("topicDetail.importButton") }}
        </button>
      </div>

      <div v-if="selectedTask" class="field-hint mt-3">
        {{ t("topicDetail.importTarget", { title: selectedTask.title }) }}
      </div>
      <div v-if="importError" class="alert alert-danger mt-3">{{ importError }}</div>
      <div v-if="importSuccess" class="alert alert-success mt-3">{{ importSuccess }}</div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <div>
          <h2 class="section-title">{{ t("topicDetail.questionsInTask") }}</h2>
          <p v-if="selectedTask" class="section-subtitle">
            {{ t("topicDetail.selectedPool", { title: selectedTask.title }) }}
          </p>
        </div>
        <div class="question-panel-actions">
          <span class="pill">{{ t("common.totalCount", { count: questionsCount }) }}</span>
          <button
            class="btn btn-outline-primary btn-sm"
            type="button"
            :disabled="!selectedTaskId"
            @click="startNewQuestion"
          >
            {{ t("topicDetail.newQuestion") }}
          </button>
        </div>
      </div>

      <div v-if="deleteError" class="alert alert-danger mb-3">{{ deleteError }}</div>
      <div v-if="questionFormSuccess" class="alert alert-success mb-3">{{ questionFormSuccess }}</div>

      <article
        v-if="openQuestionEditorId === 'new'"
        class="question-item question-editor-card"
      >
        <div class="inline-editor-title">
          {{ t("topicDetail.newQuestion") }}
        </div>
        <QuestionEditorForm
          :form="questionForm"
          :question-types="questionTypes"
          :is-matching="isMatchingForm"
          :is-single-choice="isSingleChoiceForm"
          :is-saving="isQuestionSaving"
          :can-save="Boolean(selectedTaskId)"
          :error="questionFormError"
          :success="''"
          :save-label="isQuestionSaving ? t('common.saving') : t('topicDetail.createQuestion')"
          @question-type-change="onQuestionTypeChange"
          @add-choice="addChoice"
          @remove-choice="removeChoice"
          @set-choice-correct="setChoiceCorrect"
          @add-matching-pair="addMatchingPair"
          @remove-matching-pair="removeMatchingPair"
          @save="saveQuestion"
          @cancel="resetQuestionForm"
        />
      </article>

      <div v-if="questions.length === 0" class="empty-box">{{ t("topicDetail.noQuestionsYet") }}</div>

      <article
        v-for="(question, index) in questions"
        :key="question.id"
        :class="[
          'question-item',
          { 'question-item-editing': openQuestionEditorId === question.id },
        ]"
        :style="{ '--delay': `${index * 45}ms` }"
      >
        <div class="question-head">
          <div>
            <div class="question-text" v-html="renderRichText(question.text)" />
            <div v-if="question.instruction" class="question-instruction">
              {{ t("topicDetail.instruction") }}: <span v-html="renderRichText(question.instruction)" />
            </div>
          </div>
          <div class="question-actions">
            <span class="question-type">{{ questionTypeLabel(question.question_type) }}</span>
            <button
              class="ghost-edit-btn"
              type="button"
              @click="editQuestion(question)"
            >
              {{ t("topicDetail.edit") }}
            </button>
            <button
              class="ghost-danger-btn"
              type="button"
              :disabled="deletingQuestionId === question.id"
              @click="deleteQuestion(question.id)"
            >
              {{ deletingQuestionId === question.id ? t("topicDetail.removing") : t("topicDetail.delete") }}
            </button>
          </div>
        </div>

        <div v-if="question.question_type === 'matching'" class="matching-pair-list">
          <div
            v-for="pair in question.matching_pairs"
            :key="pair.id"
            class="matching-pair-preview"
          >
            <span v-html="renderRichText(pair.left_content)" />
            <span class="matching-pair-arrow">&rarr;</span>
            <span v-html="renderRichText(pair.right_content)" />
          </div>
        </div>

        <ul v-else class="choice-list">
          <li v-for="choice in question.choices" :key="choice.id" :class="{ 'choice-correct-text': choice.is_correct }">
            <span v-html="renderRichText(choice.text)" />
            <span v-if="choice.is_correct"> {{ t("topicDetail.correctTag") }}</span>
          </li>
        </ul>

        <QuestionEditorForm
          v-if="openQuestionEditorId === question.id"
          class="inline-question-editor"
          :form="questionForm"
          :question-types="questionTypes"
          :is-matching="isMatchingForm"
          :is-single-choice="isSingleChoiceForm"
          :is-saving="isQuestionSaving"
          :can-save="Boolean(selectedTaskId)"
          :error="questionFormError"
          :success="''"
          :save-label="isQuestionSaving ? t('common.saving') : t('topicDetail.updateQuestion')"
          @question-type-change="onQuestionTypeChange"
          @add-choice="addChoice"
          @remove-choice="removeChoice"
          @set-choice-correct="setChoiceCorrect"
          @add-matching-pair="addMatchingPair"
          @remove-matching-pair="removeMatchingPair"
          @save="saveQuestion"
          @cancel="resetQuestionForm"
        />
      </article>
    </section>
  </div>
</template>

<style scoped src="./TopicDetail.css"></style>
