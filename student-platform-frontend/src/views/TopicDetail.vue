<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Question, Task, Topic } from "@/api.js";
import { sanitizeInlineRichText } from "@/utils/richText.js";

const props = defineProps(["id"]);

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
  is_active: true,
});
const taskForm = ref({
  title: "",
  description: "",
  is_active: true,
});
const taskSaveError = ref("");
const taskSaveSuccess = ref("");
const isTaskSaving = ref(false);

const getApiErrorMessage = (data) => {
  if (!data) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }

  const fields = ["detail", "src", "task", "topic", "non_field_errors"];
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

const resetImportForm = () => {
  questionFile.value = null;
  importForm.value = { is_active: true };
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
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
    loadError.value = "Failed to load topic data.";
  }
};

const createTask = async () => {
  taskSaveError.value = "";
  taskSaveSuccess.value = "";
  const title = taskForm.value.title.trim();
  if (!title) {
    taskSaveError.value = "Task title is required.";
    return;
  }

  isTaskSaving.value = true;
  try {
    const createdTask = await Task.save({
      topic: Number(props.id),
      title,
      description: taskForm.value.description.trim(),
      is_active: taskForm.value.is_active,
    });
    taskForm.value = { title: "", description: "", is_active: true };
    selectedTaskId.value = String(createdTask.id);
    taskSaveSuccess.value = "Task created.";
    await getTasks();
    await getQuestions();
  } catch (error) {
    taskSaveError.value =
      error?.response?.data?.title?.[0] ||
      error?.response?.data?.detail ||
      "Could not create task.";
  } finally {
    isTaskSaving.value = false;
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
    importError.value = "Create or select a task first.";
    return;
  }
  if (!questionFile.value) {
    importError.value = "Choose a .xls or .xlsx file.";
    return;
  }

  const formData = new FormData();
  formData.append("src", questionFile.value);
  formData.append("is_active", importForm.value.is_active ? "true" : "false");

  isImporting.value = true;
  try {
    const response = await Task.importQuestions(selectedTaskId.value, formData);
    importSuccess.value = `Imported ${response.imported_count} question(s).`;
    resetImportForm();
    await Promise.all([getTasks(), getQuestions()]);
  } catch (error) {
    importError.value =
      getApiErrorMessage(error?.response?.data) || "Could not import questions.";
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
const tasksCount = computed(() => tasks.value.length);
const selectedTask = computed(() =>
  tasks.value.find((task) => String(task.id) === String(selectedTaskId.value)),
);
const selectedFileName = computed(() => questionFile.value?.name || "No file selected");

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
  resetImportForm();
  await getQuestions();
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
          <div class="metric-label">Tasks</div>
          <div class="metric-value">{{ tasksCount }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Selected questions</div>
          <div class="metric-value">{{ questionsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger mt-3">{{ loadError }}</div>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Tasks in Topic</h2>
        <span class="pill">{{ tasksCount }} total</span>
      </div>

      <div class="row g-3 align-items-end">
        <div class="col-md-4">
          <label class="form-label">Current task</label>
          <select v-model="selectedTaskId" class="form-select">
            <option value="">No task selected</option>
            <option v-for="taskItem in tasks" :key="taskItem.id" :value="String(taskItem.id)">
              {{ taskItem.title }}
            </option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label">New task title</label>
          <input v-model="taskForm.title" class="form-control" type="text" placeholder="Task title" />
        </div>
        <div class="col-md-3">
          <label class="form-label">Description</label>
          <input v-model="taskForm.description" class="form-control" type="text" placeholder="Optional" />
        </div>
        <div class="col-md-2">
          <button class="btn btn-primary w-100" type="button" :disabled="isTaskSaving" @click="createTask">
            {{ isTaskSaving ? "Creating..." : "Create task" }}
          </button>
        </div>
      </div>

      <div class="form-check mt-3">
        <input id="task-active" v-model="taskForm.is_active" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="task-active">Active</label>
      </div>

      <div v-if="selectedTask" class="field-hint mt-3">
        Selected pool: {{ selectedTask.title }}.
      </div>
      <div v-if="taskSaveError" class="alert alert-danger mt-3">{{ taskSaveError }}</div>
      <div v-if="taskSaveSuccess" class="alert alert-success mt-3">{{ taskSaveSuccess }}</div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Import Questions</h2>
        <span class="pill">.xls / .xlsx</span>
      </div>

      <div class="import-grid">
        <div>
          <label class="form-label">Question file</label>
          <label class="file-drop">
            <input
              ref="fileInputRef"
              type="file"
              accept=".xls,.xlsx"
              class="file-input"
              @change="onQuestionFileChange"
            />
            <span class="file-name">{{ selectedFileName }}</span>
            <span class="file-action">Choose file</span>
          </label>
        </div>

        <div class="import-state">
          <label class="form-label d-block">Question state</label>
          <div class="form-check mt-2">
            <input id="import-active" v-model="importForm.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="import-active">Active</label>
          </div>
        </div>

        <button
          class="btn btn-primary import-btn"
          type="button"
          :disabled="isImporting || !selectedTaskId"
          @click="importQuestions"
        >
          {{ isImporting ? "Importing..." : "Import questions" }}
        </button>
      </div>

      <div v-if="selectedTask" class="field-hint mt-3">
        Import target: {{ selectedTask.title }}.
      </div>
      <div v-if="importError" class="alert alert-danger mt-3">{{ importError }}</div>
      <div v-if="importSuccess" class="alert alert-success mt-3">{{ importSuccess }}</div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Questions in Task</h2>
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
            <span v-html="renderRichText(choice.text)" />
            <span v-if="choice.is_correct"> (correct)</span>
          </li>
        </ul>
      </article>
    </section>
  </div>
</template>

<style scoped src="./TopicDetail.css"></style>
