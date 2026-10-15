<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import axios from "axios";
import { useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { apiError } from "@/utils/apiError";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { useI18n } from "vue-i18n";
import { Group, Question, Task, Topic } from "@/api.js";
import { sanitizeInlineRichText } from "@/utils/richText.js";
import QuestionImageGallery from "@/components/QuestionImageGallery.vue";
import QuestionEditorForm from "./QuestionEditorForm.vue";
import { useUnsavedChanges } from '@/composables/useUnsavedChanges';

import TaskAssignment from '@/components/TaskAssignment.vue';
import QuestionPreview from '@/components/QuestionPreview.vue';
import { allMaterialChoices } from '@/composables/useMaterialChoices';
const props = defineProps({ id: String, taskId: String, workspace: Boolean });
const previewQuestion = ref(null);
const assignmentBusy = ref(false);
const mobileEditor = ref(false);
const editorHeading = ref(null);
const questionsHeading = ref(null);
watch(mobileEditor, async (editing) => {
  if (!props.workspace || !window.matchMedia('(max-width: 760px)').matches) return;
  await nextTick();
  (editing ? editorHeading.value : questionsHeading.value)?.focus();
});
const { t } = useI18n();
const route = useRoute();
const libraryReturnQuery = computed(() => ({
  view: 'materials',
  q: typeof route.query.libraryQ === 'string' ? route.query.libraryQ : undefined,
  subject: typeof route.query.librarySubject === 'string' && /^\d+$/.test(route.query.librarySubject) ? route.query.librarySubject : undefined,
  page: typeof route.query.libraryPage === 'string' && /^[1-9]\d*$/.test(route.query.libraryPage) && Number.isSafeInteger(Number(route.query.libraryPage)) ? route.query.libraryPage : undefined,
}));
const auth = useAuthStore();
const activeTab = ref('questions');
const newTaskOpen = ref(false);
const assignmentGroups = ref([]);
const assignmentGroup = ref('');
const assignmentOpen = ref(false);
const assignmentError = ref('');
const openAssignment = async () => {
  assignmentOpen.value = true;
  assignmentError.value = '';
  try {
    const response = await Group.filter({teacher_subject: topic.value.subject});
    assignmentGroups.value = response.results ?? response;
  } catch (error) { assignmentError.value = apiError(error); }
};
const preview = ref(null);
const undoToken = ref('');
const undoConfirm = ref(false);
const draftMessage = ref('');
const discardConfirm = ref(false);
const undoKey = () => `import-undo:${auth.user?.id}:${selectedTaskId.value}`;
const draftKey = () => `question-draft:${auth.user?.id}:${props.id}:${selectedTaskId.value}`;
const discardQuestionDraft = () => {
  try { sessionStorage.removeItem(draftKey()); } catch {}
  resetQuestionForm(); draftMessage.value = ''; discardConfirm.value = false;
};
const restoreDraft = () => {
  try {
    const draft = JSON.parse(sessionStorage.getItem(draftKey()) || 'null');
    if (draft) { questionForm.value = {...draft, pending_images: []}; openQuestionEditorId.value = draft.id || 'new'; draftMessage.value = t('ux.draftRestored') + ' ' + t('ux.draftFiles'); }
  } catch { /* Storage may be unavailable. */ }
};
const undoImport = async () => {
  undoConfirm.value = false;
  if (contextBusy.value) return;
  isImporting.value = true;
  const taskId = selectedTaskId.value;
  const storageKey = undoKey();
  try {
    await axios.post(`/api/task/${taskId}/undo-import/`, {token: undoToken.value});
    undoToken.value = '';
    try { sessionStorage.removeItem(storageKey); } catch {}
    importSuccess.value = t('ux.undone');
    await Promise.all([getTasks(), getQuestions()]);
  } catch (error) { importError.value = apiError(error); }
  finally { isImporting.value = false; }
};

const topic = ref({});
const tasks = ref([]);
const selectedTaskId = ref("");
const questions = ref([]);
const loadError = ref("");
const loading = ref(true);
const questionsLoading = ref(false);
const questionsError = ref("");
const pendingDelete = ref(null);
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
const editorSnapshot = () => JSON.stringify({...questionForm.value, pending_images: questionForm.value.pending_images.map(image => image.file.name)});
const editorBaseline = ref(editorSnapshot());
const editorHasChanges = () => Boolean(openQuestionEditorId.value && editorSnapshot() !== editorBaseline.value);
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
const contextBusy = computed(() => isQuestionSaving.value || isTaskSaving.value || isCurrentTaskSaving.value || isImporting.value || Boolean(deletingQuestionId.value) || assignmentBusy.value);
const { pendingLeave, finishLeave, guardAction } = useUnsavedChanges(() =>
  Boolean((props.workspace && editorHasChanges()) || questionForm.value.pending_images.length || taskForm.value.title.trim() || taskForm.value.description.trim()
    || (selectedTask.value && (Number(currentTaskForm.value.questions_per_attempt) !== selectedTask.value.questions_per_attempt
      || Number(currentTaskForm.value.passing_correct_answers) !== selectedTask.value.passing_correct_answers))),
  () => contextBusy.value,
);
const changeTask = (event) => {
  const nextTask = event.target.value;
  event.target.value = selectedTaskId.value;
  guardAction(() => { selectedTaskId.value = nextTask; });
};
const replaceEditor = (action) => guardAction(() => {
  if (openQuestionEditorId.value) {
    try { sessionStorage.removeItem(draftKey()); } catch {}
    draftMessage.value = '';
  }
  action();
}, editorHasChanges());

function createBlankQuestionForm() {
  return {
    id: null,
    question_type: "single_choice",
    text: "",
    instruction: "",
    is_active: true,
    images: [],
    pending_images: [],
    removed_image_ids: [],
    choices: [
      { id: null, text: "", is_correct: false, order: 1 },
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
  preview.value = null;
  questionFile.value = null;
  importForm.value = { question_type: "single_choice" };
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
};

const resetQuestionForm = () => {
  openQuestionEditorId.value = null;
  revokePendingImagePreviews();
  questionForm.value = createBlankQuestionForm();
  editorBaseline.value = editorSnapshot();
  questionFormError.value = "";
  questionFormSuccess.value = "";
  openQuestionEditorId.value = null;
};

const getTopic = async () => {
  const response = await Topic.get(props.id);
  topic.value = response;
};

const getTasks = async () => {
  if (props.workspace) {
    tasks.value = [await Task.get(props.taskId)];
    if (!selectedTaskId.value) selectedTaskId.value = String(props.taskId);
    return;
  }
  tasks.value = await allMaterialChoices(Task, { topic: props.id, ordering: "title" });
  if (!selectedTaskId.value && tasks.value.length > 0) {
    selectedTaskId.value = String(tasks.value[0].id);
  }
};

let questionsRequest = 0;
const getQuestions = async () => {
  const request = ++questionsRequest;
  questionsError.value = "";
  questionsLoading.value = true;
  questions.value = [];
  if (!selectedTaskId.value) {
    questionsLoading.value = false;
    return;
  }
  try {
    const response = await allMaterialChoices(Question, { task: selectedTaskId.value });
    if (request === questionsRequest) questions.value = response;
  } catch (error) {
    if (request === questionsRequest) questionsError.value = apiError(error, 'workstation.materials.questionsError');
  } finally {
    if (request === questionsRequest) questionsLoading.value = false;
  }
};

const loadTopicPage = async () => {
  loading.value = true;
  loadError.value = "";
  try {
    const previousTaskId = selectedTaskId.value;
    await Promise.all([getTopic(), getTasks()]);
    // Selection changes load questions in the watcher; avoid a second request
    // clearing its list while it decides whether to open a new question.
    if (selectedTaskId.value === previousTaskId) await getQuestions();
  } catch {
    loadError.value = t("topicDetail.loadError");
  } finally {
    loading.value = false;
  }
};

const createTask = async () => {
  if (contextBusy.value) return;
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
    taskSaveError.value = apiError(error, "topicDetail.errors.createTask");
  } finally {
    isTaskSaving.value = false;
  }
};

const updateCurrentTaskSettings = async () => {
  if (contextBusy.value) return;
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
      apiError(error, "topicDetail.errors.saveSettings");
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
    questionFormError.value = t("ux.chooseCorrect");
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
      is_correct: index === firstCorrectIndex,
    }));
  }
};

const startNewQuestion = () => {
  openQuestionEditorId.value = null;
  revokePendingImagePreviews();
  questionForm.value = createBlankQuestionForm();
  editorBaseline.value = editorSnapshot();
  questionFormError.value = "";
  questionFormSuccess.value = "";
  deleteError.value = "";
  importError.value = "";
  importSuccess.value = "";
  openQuestionEditorId.value = "new";
  restoreDraft();
};

const editQuestion = (question) => {
  openQuestionEditorId.value = null;
  revokePendingImagePreviews();
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
    images: [...(question.images ?? [])],
    pending_images: [],
    removed_image_ids: [],
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
  editorBaseline.value = editorSnapshot();
};

const revokePendingImagePreviews = () => {
  for (const image of questionForm.value.pending_images ?? []) {
    URL.revokeObjectURL(image.preview_url);
  }
};

const addQuestionImages = (files) => {
  const existingFiles = new Set(
    (questionForm.value.pending_images ?? []).map(
      ({ file }) => `${file.name}:${file.size}:${file.lastModified}`,
    ),
  );
  const additions = [];
  for (const file of files) {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!existingFiles.has(key)) {
      additions.push({
        file,
        preview_url: URL.createObjectURL(file),
      });
      existingFiles.add(key);
    }
  }
  questionForm.value.pending_images.push(...additions);
};

const removePendingQuestionImage = (index) => {
  const [removed] = questionForm.value.pending_images.splice(index, 1);
  if (removed) {
    URL.revokeObjectURL(removed.preview_url);
  }
};

const removeSavedQuestionImage = (imageId) => {
  questionForm.value.images = questionForm.value.images.filter(
    (image) => image.id !== imageId,
  );
  if (!questionForm.value.removed_image_ids.includes(imageId)) {
    questionForm.value.removed_image_ids.push(imageId);
  }
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
  if (contextBusy.value) return;
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
  const savingForm = questionForm.value;
  const savingDraftKey = draftKey();
  try {
    const wasEditing = Boolean(payload.id);
    const savedQuestion = await Question.save(payload);
    savingForm.id = savedQuestion.id;

    for (const imageId of savingForm.removed_image_ids) {
      await Question.deleteImage(savedQuestion.id, imageId);
    }
    savingForm.removed_image_ids = [];

    const pendingFiles = savingForm.pending_images.map(({ file }) => file);
    if (pendingFiles.length > 0) {
      await Question.uploadImages(savedQuestion.id, pendingFiles);
    }

    const successMessage = wasEditing
      ? t("topicDetail.questionUpdated")
      : t("topicDetail.questionCreated");
    try { sessionStorage.removeItem(savingDraftKey); } catch {}
    draftMessage.value = "";
    resetQuestionForm();
    questionFormSuccess.value = successMessage;
    await getQuestions();
    if (props.workspace) { await getTasks(); mobileEditor.value = false; }
  } catch (error) {
    questionFormError.value =
      apiError(error, "topicDetail.errors.saveQuestion");
  } finally {
    isQuestionSaving.value = false;
  }
};

const onQuestionFileChange = (event) => {
  preview.value = null;
  importError.value = "";
  importSuccess.value = "";
  questionFile.value = event.target.files?.[0] ?? null;
};

const importQuestions = async (commit = false) => {
  if (contextBusy.value) return;
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
  formData.append("preview", commit ? "false" : "true");
  formData.append("question_type", importForm.value.question_type);

  isImporting.value = true;
  const importingTask = selectedTaskId.value;
  const importingUndoKey = undoKey();
  try {
    const response = await Task.importQuestions(importingTask, formData);
    if (!commit) { preview.value = response; return; }
    preview.value = null;
    if (response.undo_token) {
      undoToken.value = response.undo_token;
      try { sessionStorage.setItem(importingUndoKey, undoToken.value); } catch {}
    }
    importSuccess.value = t("ux.imported", {count: response.imported_count, duplicates: response.duplicate_count});
    resetImportForm();
    await Promise.all([getTasks(), getQuestions()]);
  } catch (error) {
    importError.value = apiError(error, "ux.invalidFile");
  } finally {
    isImporting.value = false;
  }
};

const deleteQuestion = async (questionId) => {
  if (contextBusy.value) return;
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
    if (props.workspace) await getTasks();
  } catch (error) {
    deleteError.value = apiError(error, "topicDetail.errors.deleteQuestion");
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

onBeforeUnmount(() => {
  revokePendingImagePreviews();
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
  try { undoToken.value = sessionStorage.getItem(undoKey()) || ""; } catch { undoToken.value = ""; }
  preview.value = null;
  restoreDraft();
  if (props.workspace && !openQuestionEditorId.value && !questions.value.length && !questionsError.value) {
    startNewQuestion(); mobileEditor.value = true;
  }
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
watch(() => importForm.value.question_type, () => { preview.value = null; });
watch(questionForm, (form) => {
  if (!openQuestionEditorId.value) return;
  try { sessionStorage.setItem(draftKey(), JSON.stringify({...form, pending_images: []})); draftMessage.value = t('ux.savedDraft') + (form.pending_images.length ? ' ' + t('ux.draftFiles') : ''); } catch { draftMessage.value = t('ux.unsavedDraft'); }
}, {deep: true, flush: 'sync'});
</script>

<template>
  <div class="topic-page" :class="{ 'test-workspace': workspace }">
    <nav class="page-breadcrumbs" :aria-label="t('workstation.group.breadcrumbs')">
      <router-link :to="{name:'teacher-home',query: libraryReturnQuery}">{{ t('workstation.nav.materials') }}</router-link>
      <router-link v-if="route.query.group" :to="{name:'group-overview', params:{id:route.query.group}}">{{ t('ux.schedule') }}</router-link>
      <router-link v-if="topic.subject && !workspace" :to="{name:'subject-detail', params:{id:topic.subject}, query:{group:route.query.group}}">{{ topic.subject_name || t('common.subject') }}</router-link>
      <span aria-current="page">{{ workspace ? t('materialsFlow.editor') : topic.title }}</span>
    </nav>
    <header v-if="!workspace" class="topic-heading">
      <div>
        <h1 class="topic-title">{{ topic.title || t("common.untitledLesson") }}</h1>
        <p class="topic-description">{{ topic.description || t("common.noDescriptionYet") }}</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <div class="metric-label">{{ t("common.status") }}</div>
          <div class="metric-value">{{ loading || loadError ? '—' : topic.is_active ? t("common.active") : t("common.inactive") }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ t("common.tasks") }}</div>
          <div class="metric-value">{{ loading || loadError ? '—' : tasksCount }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ t("topicDetail.selectedQuestions") }}</div>
          <div class="metric-value">{{ loading || loadError || questionsLoading || questionsError ? '—' : questionsCount }}</div>
        </div>
      </div>
    </header>

    <div v-if="loadError" class="alert alert-danger mt-3" role="alert">{{ loadError }} <button class="btn btn-link" @click="loadTopicPage">{{ t('ux.retry') }}</button></div>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <template v-if="!loading && !loadError">

    <header v-if="workspace && selectedTask" class="flow-heading">
      <div><h1>{{ selectedTask.title }}</h1><p>{{ topic.subject_name }} · {{ t('materialsFlow.questions', { count: questionsCount }) }}</p><p>{{ t('materialsFlow.attempt', { count: selectedTask.questions_per_attempt, passing: selectedTask.passing_correct_answers }) }}</p></div>
      <button v-if="activeTab !== 'assign'" class="btn btn-primary" :disabled="contextBusy" @click="activeTab = 'assign'">{{ t('materialsFlow.assign') }}</button>
    </header>
    <section class="surface-card task-workspace-toolbar">
    <label v-if="!workspace" class="field-wrap">{{ t('ux.chooseTask') }}<select :value="selectedTaskId" :disabled="contextBusy" @change="changeTask" class="form-select"><option v-for="task in tasks" :key="task.id" :value="String(task.id)">{{ task.title }}</option></select></label>
    <nav class="page-tabs workspace-tabs" :aria-label="t('materialsFlow.editor')"><button v-for="tab in (workspace ? ['questions', 'settings', 'import', 'assign'] : ['questions', 'settings', 'import'])" :key="tab" class="btn" :class="{ active: activeTab === tab }" :aria-pressed="activeTab === tab" :disabled="assignmentBusy" @click="activeTab = tab">{{ t(tab === 'questions' ? 'ux.editQuestions' : tab === 'settings' ? 'ux.taskSettings' : tab === 'assign' ? 'materialsFlow.stepAssign' : 'ux.importQuestions') }}</button></nav>
    <div v-if="!workspace" class="workspace-actions"><button class="btn btn-outline-primary" :disabled="contextBusy" @click="activeTab = 'settings'; newTaskOpen = true">{{ t('ux.createTask') }}</button>
    <router-link class="btn btn-primary" v-if="route.query.group && selectedTask" :to="{name: 'group-overview', params:{id:route.query.group}, query:{task:selectedTaskId, topic:props.id}}">{{ t('ux.assignTask') }}</router-link>
    <button v-else-if="selectedTask" class="btn btn-primary" @click="openAssignment">{{ t('ux.assignTask') }}</button>
    </div>
    </section>
    <Transition name="reveal"><TaskAssignment v-if="workspace && activeTab === 'assign' && selectedTask" :key="selectedTask.id" :task="selectedTask" :blocked="editorHasChanges() || isCurrentTaskSaving || Number(currentTaskForm.questions_per_attempt) !== selectedTask.questions_per_attempt || Number(currentTaskForm.passing_correct_answers) !== selectedTask.passing_correct_answers" @busy="assignmentBusy = $event" /></Transition>
    <p v-if="draftMessage" class="draft-notice" role="status">{{ draftMessage }} <button class="btn btn-link" :disabled="contextBusy" @click="discardConfirm = true">{{ t('ux.discardDraft') }}</button></p>
    <ConfirmDialog v-if="discardConfirm" :title="t('ux.discardDraft')" :description="t('ux.discardConfirm')" :confirm-label="t('ux.discardDraft')" @cancel="discardConfirm = false" @confirm="discardQuestionDraft" />
    <div v-if="assignmentOpen" class="surface-card p-3">
      <label class="field-wrap">{{ t('ux.chooseGroup') }}<select v-model="assignmentGroup" class="form-select"><option value="">—</option><option v-for="group in assignmentGroups" :key="group.id" :value="group.id">{{ group.name }}</option></select></label>
      <p v-if="assignmentError" role="alert">{{ assignmentError }}</p>
      <p v-if="!assignmentGroups.length && !assignmentError">{{ t('ux.noAssignedGroups') }}</p>
      <router-link class="btn btn-outline-primary mt-3" v-if="assignmentGroup" :to="{name:'group-overview',params:{id:assignmentGroup},query:{task:selectedTaskId,topic:props.id}}">{{ t('ux.schedule') }}</router-link>
    </div>
    <section v-show="activeTab === 'settings'" class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t(workspace ? "ux.taskSettings" : "topicDetail.tasksInLesson") }}</h2>
        <span v-if="!workspace" class="pill">{{ t("common.totalCount", { count: tasksCount }) }}</span>
      </div>

      <div class="task-sections">
        <div class="task-subsection current-task-section">
          <h3 class="task-subsection-title">{{ t("topicDetail.currentTask") }}</h3>

          <div class="task-settings-grid">
            <div v-if="!workspace">
              <label class="form-label" for="topic-field-1">{{ t("common.task") }}</label>
              <select id="topic-field-1" :value="selectedTaskId" :disabled="contextBusy" @change="changeTask" class="form-select">
                <option value="">{{ t("topicDetail.noTaskSelected") }}</option>
                <option v-for="taskItem in tasks" :key="taskItem.id" :value="String(taskItem.id)">
                  {{ taskItem.title }}
                </option>
              </select>
            </div>

            <div>
              <label class="form-label" for="topic-field-2">{{ t("common.questions") }}</label>
              <input id="topic-field-2"
                v-model.number="currentTaskForm.questions_per_attempt"
                class="form-control"
                :disabled="!selectedTask"
                min="1"
                step="1"
                type="number"
              />
            </div>

            <div>
              <label class="form-label" for="topic-field-3">{{ t("topicDetail.passFrom") }}</label>
              <input id="topic-field-3"
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
              :disabled="!selectedTask || contextBusy"
              @click="updateCurrentTaskSettings"
            >
              {{ isCurrentTaskSaving ? t("common.saving") : t("topicDetail.saveSettings") }}
            </button>
          </div>

          <div v-if="selectedTask" class="field-hint mt-3">
            {{ t("topicDetail.selectedPool", { title: selectedTask.title }) }}
          </div>
          <div v-if="currentTaskSaveError" class="alert alert-danger mt-3" role="alert">{{ currentTaskSaveError }}</div>
          <div v-if="currentTaskSaveSuccess" class="alert alert-success mt-3" role="status">{{ currentTaskSaveSuccess }}</div>
        </div>

        <details v-if="!workspace" :open="newTaskOpen" class="task-subsection" @toggle="newTaskOpen = $event.target.open">
          <summary>{{ t("topicDetail.newTask") }}</summary>

          <div class="new-task-grid">
            <div>
              <label class="form-label" for="topic-field-4">{{ t("common.title") }}</label>
              <input id="topic-field-4"
                v-model="taskForm.title"
                class="form-control"
                type="text"
                :placeholder="t('topicDetail.taskTitlePlaceholder')"
              />
            </div>

            <div>
              <label class="form-label" for="topic-field-5">{{ t("common.description") }}</label>
              <input id="topic-field-5"
                v-model="taskForm.description"
                class="form-control"
                type="text"
                :placeholder="t('common.optional')"
              />
            </div>

            <div>
              <label class="form-label" for="topic-field-6">{{ t("common.questions") }}</label>
              <input id="topic-field-6"
                v-model.number="taskForm.questions_per_attempt"
                class="form-control"
                min="1"
                step="1"
                type="number"
              />
            </div>

            <div>
              <label class="form-label" for="topic-field-7">{{ t("topicDetail.passFrom") }}</label>
              <input id="topic-field-7"
                v-model.number="taskForm.passing_correct_answers"
                class="form-control"
                min="1"
                :max="taskForm.questions_per_attempt"
                step="1"
                type="number"
              />
            </div>

            <button class="btn btn-primary new-task-btn" type="button" :disabled="contextBusy" @click="createTask">
              {{ isTaskSaving ? t("common.creating") : t("topicDetail.createTask") }}
            </button>
          </div>

          <div class="form-check mt-3">
            <input id="task-active" v-model="taskForm.is_active" class="form-check-input" type="checkbox" />
            <label class="form-check-label" for="task-active">{{ t("common.active") }}</label>
          </div>

          <div v-if="taskSaveError" class="alert alert-danger mt-3" role="alert">{{ taskSaveError }}</div>
          <div v-if="taskSaveSuccess" class="alert alert-success mt-3" role="status">{{ taskSaveSuccess }}</div>
        </details>
      </div>
    </section>

    <section v-show="activeTab === 'import'" class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t("topicDetail.importQuestions") }}</h2>
        <span class="pill">.xls / .xlsx</span>
      </div>

      <p class="helper-copy">{{ t('ux.importHelp') }}</p>
      <a class="btn btn-outline-primary template-download" :href="`/templates/${importForm.question_type}.xlsx`" download>{{ t('ux.template') }}</a>
      <div class="import-grid">
        <div>
          <label class="form-label" for="topic-field-8">{{ t("topicDetail.questionType") }}</label>
          <select id="topic-field-8" :disabled="contextBusy" v-model="importForm.question_type" class="form-select">
            <option v-for="type in questionTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="form-label" for="question-import-file">{{ t("topicDetail.questionFile") }}</label>
          <label class="file-drop">
            <input
              ref="fileInputRef"
              id="question-import-file" :disabled="contextBusy"
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
          :disabled="contextBusy || !selectedTaskId"
          @click="importQuestions(false)"
        >
          {{ isImporting ? t("topicDetail.importing") : t("ux.previewImport") }}
        </button>
      </div>

      <div v-if="selectedTask" class="field-hint mt-3">
        {{ t("topicDetail.importTarget", { title: selectedTask.title }) }}
      </div>
      <div v-if="preview" class="alert alert-info">
        <p>{{ t('ux.importPreview', {count: preview.imported_count, duplicates: preview.duplicate_count}) }}</p>
        <ul><li v-for="(text, index) in preview.questions" :key="index" v-html="sanitizeInlineRichText(text)"></li></ul>
        <button class="btn btn-primary" :disabled="contextBusy" @click="importQuestions(true)">{{ t('ux.confirmImport') }}</button>
      </div>
      <button v-if="undoToken" class="btn btn-outline-danger" @click="undoConfirm = true">{{ t('ux.undoImport') }}</button>
      <ConfirmDialog v-if="undoConfirm" :title="t('ux.undoImport')" :description="t('ux.undoConfirm')" :confirm-label="t('ux.undoImport')" @confirm="undoImport" @cancel="undoConfirm = false" />
      <div v-if="importError" class="alert alert-danger mt-3" role="alert">{{ importError }}</div>
      <div v-if="importSuccess" class="alert alert-success mt-3" role="status">{{ importSuccess }}</div>
    </section>

    <section v-if="!workspace" v-show="activeTab === 'questions'" class="surface-card panel-card">
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
            :disabled="!selectedTaskId || contextBusy"
            @click="replaceEditor(startNewQuestion)"
          >
            {{ t("topicDetail.newQuestion") }}
          </button>
        </div>
      </div>

      <div v-if="deleteError" class="alert alert-danger mb-3" role="alert">{{ deleteError }}</div>
      <div v-if="questionFormSuccess" class="alert alert-success mb-3" role="status">{{ questionFormSuccess }}</div>

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
          :is-saving="contextBusy"
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
          @add-images="addQuestionImages"
          @remove-pending-image="removePendingQuestionImage"
          @remove-saved-image="removeSavedQuestionImage"
          @save="saveQuestion"
          @cancel="guardAction(resetQuestionForm, editorHasChanges())"
        />
      </article>

      <p v-if="questionsLoading" role="status">{{ t('common.loading') }}</p>
      <div v-else-if="questionsError" class="alert alert-danger" role="alert">{{ questionsError }} <button class="btn btn-link" @click="getQuestions">{{ t('ux.retry') }}</button></div>
      <div v-else-if="questions.length === 0" class="empty-box">{{ t("topicDetail.noQuestionsYet") }}</div>

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
              :disabled="contextBusy" @click="replaceEditor(() => editQuestion(question))"
            >
              {{ t("topicDetail.edit") }}
            </button>
            <button
              class="ghost-danger-btn"
              type="button"
              :disabled="contextBusy"
              @click="pendingDelete = question.id"
            >
              {{ deletingQuestionId === question.id ? t("topicDetail.removing") : t("topicDetail.delete") }}
            </button>
          </div>
        </div>

        <QuestionImageGallery
          v-if="question.images?.length"
          :images="question.images"
          compact
        />

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
          :is-saving="contextBusy"
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
          @add-images="addQuestionImages"
          @remove-pending-image="removePendingQuestionImage"
          @remove-saved-image="removeSavedQuestionImage"
          @save="saveQuestion"
          @cancel="guardAction(resetQuestionForm, editorHasChanges())"
        />
      </article>
    </section>

    <div v-if="workspace && questionFormSuccess" class="alert alert-success" role="status">{{ questionFormSuccess }}</div>
    <section v-if="workspace" v-show="activeTab === 'questions'" class="flow-questions" :class="{ 'show-editor': mobileEditor }">
      <aside class="surface-card flow-question-list">
        <h2 ref="questionsHeading" tabindex="-1">{{ t('common.questions') }} <span class="question-count">{{ questionsCount }}</span></h2>
        <button class="btn btn-outline-primary" :disabled="contextBusy" @click="replaceEditor(() => { startNewQuestion(); mobileEditor = true; })">{{ t('topicDetail.newQuestion') }}</button>
        <p v-if="questionsLoading" role="status">{{ t('common.loading') }}</p>
        <div v-else-if="questionsError" role="alert">{{ questionsError }} <button class="btn btn-link" @click="getQuestions">{{ t('ux.retry') }}</button></div>
        <p v-else-if="!questions.length">{{ t('topicDetail.noQuestionsYet') }}</p>
        <ol><li v-for="(question, index) in questions" :key="question.id"><button class="flow-question-button" :class="{ selected: openQuestionEditorId === question.id }" :aria-pressed="openQuestionEditorId === question.id" :disabled="contextBusy" @click="replaceEditor(() => { editQuestion(question); mobileEditor = true; })"><span class="flow-number">{{ index + 1 }}</span><span><span class="flow-question-text" v-html="renderRichText(question.text)" /><small>{{ questionTypeLabel(question.question_type) }}{{ question.is_active ? '' : ' · ' + t('common.inactive') }}</small></span></button></li></ol>
      </aside>
      <div class="surface-card flow-editor">
        <button class="btn btn-link flow-back" @click="mobileEditor = false">{{ t('materialsFlow.list') }}</button>
        <div v-if="deleteError" class="alert alert-danger" role="alert">{{ deleteError }}</div>
        <template v-if="openQuestionEditorId">
          <div class="flow-editor-head"><h2 ref="editorHeading" tabindex="-1">{{ questionForm.id ? t('materialsFlow.editingQuestion', { number: questions.findIndex(q => q.id === questionForm.id) + 1 }) : t('topicDetail.newQuestion') }}</h2><div class="flow-editor-actions"><button class="btn btn-link" :disabled="!questionForm.text" @click="previewQuestion = questionForm">{{ t('materialsFlow.previewAction') }}</button><button v-if="questionForm.id" class="btn btn-outline-danger" :disabled="contextBusy" @click="pendingDelete = questionForm.id">{{ t('common.remove') }}</button></div></div>
        <QuestionEditorForm
          :form="questionForm"
          :question-types="questionTypes"
          :is-matching="isMatchingForm"
          :is-single-choice="isSingleChoiceForm"
          :is-saving="contextBusy"
          :can-save="Boolean(selectedTaskId)"
          :error="questionFormError"
          :success="''"
          :save-label="isQuestionSaving ? t('common.saving') : t(questionForm.id ? 'topicDetail.updateQuestion' : 'topicDetail.createQuestion')"
          @question-type-change="onQuestionTypeChange"
          @add-choice="addChoice"
          @remove-choice="removeChoice"
          @set-choice-correct="setChoiceCorrect"
          @add-matching-pair="addMatchingPair"
          @remove-matching-pair="removeMatchingPair"
          @add-images="addQuestionImages"
          @remove-pending-image="removePendingQuestionImage"
          @remove-saved-image="removeSavedQuestionImage"
          @save="saveQuestion"
          @cancel="guardAction(resetQuestionForm, editorHasChanges())"
        />
        </template>
        <p v-else class="empty-box">{{ t('materialsFlow.selectQuestion') }}</p>
      </div>
    </section>
    <QuestionPreview v-if="previewQuestion" :question="previewQuestion" @close="previewQuestion = null" />
    <ConfirmDialog v-if="pendingDelete" :title="t('workstation.materials.removeQuestion')" :description="t('workstation.materials.removeQuestionHint')" :confirm-label="t('common.remove')" @cancel="pendingDelete = null" @confirm="deleteQuestion(pendingDelete); pendingDelete = null" />
    </template>
    <ConfirmDialog v-if="pendingLeave" :title="t('workstation.materials.leaveTitle')" :description="t('workstation.materials.leaveHint')" :confirm-label="t('workstation.materials.leave')" @cancel="finishLeave(false)" @confirm="finishLeave(true)" />
  </div>
</template>

<style scoped src="./TopicDetail.css"></style>

<style scoped>
.flow-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:24px; margin:12px 0; }
.flow-heading h1 { font-size:30px; overflow-wrap:anywhere; }
.flow-heading p { color:var(--ink-soft); margin:8px 0 0; }
.flow-questions { display:grid; grid-template-columns:minmax(200px, 260px) minmax(0, 1fr); gap:24px; }
.flow-question-list, .flow-editor { padding:24px; min-width:0; }
.flow-question-list { align-self:start; background:transparent; border:0; padding:16px 0; }
.flow-question-list > .btn { width:100%; }
.question-count { color:var(--ink-soft); margin-left:6px; font-size:14px; font-weight:400; }
.test-workspace .task-workspace-toolbar { border:0; border-radius:0; background:transparent; padding:0; }
.test-workspace .workspace-tabs { width:100%; }
.flow-question-list h2, .flow-editor h2 { font-size:20px; margin:0 0 20px; }
.flow-question-list ol { list-style:none; padding:0; margin:16px 0 0; }
.flow-question-button { display:flex; gap:12px; text-align:left; width:100%; padding:16px 12px; border:0; border-radius:8px; background:transparent; color:var(--ink); transition:background-color var(--motion-fast); }
.flow-question-button:hover { background:var(--bg-0); }
.flow-question-button.selected { background:#edf2fd; color:#244aa7; }
.flow-question-button > span:last-child { min-width:0; }
.flow-question-text { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere; }
.flow-question-button small { display:block; margin-top:6px; color:var(--ink-soft); }
.flow-number { font-variant-numeric:tabular-nums; }
.flow-editor-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:20px; }
.flow-editor-actions { display:flex; flex-wrap:wrap; gap:8px; }
.flow-back { display:none; }
@media(max-width:760px) {
  .test-workspace { gap:12px; }
  .test-workspace .flow-heading { margin:0; gap:8px; }
  .test-workspace .flow-heading h1 { font-size:22px; margin:0; }
  .test-workspace .flow-heading p { font-size:12px; margin-top:4px; }
  .test-workspace .flow-heading > .btn { display:none; }
  .test-workspace .draft-notice { padding:8px 12px; gap:0 8px; font-size:12px; }
  .test-workspace .draft-notice .btn { padding:4px 0; font-size:12px; }
  .flow-editor-head { align-items:center; gap:4px 8px; margin-bottom:16px; }
  .flow-editor-head h2 { margin:0; font-size:18px; }
  .flow-editor-actions { gap:4px; }
  .flow-editor-actions .btn { padding:6px 0; font-size:12px; }
  .flow-editor { padding:20px 16px; }
  .test-workspace .workspace-tabs { gap:14px; }
  .test-workspace .workspace-tabs > .btn { flex:0 0 auto; font-size:13px; }
  .flow-heading { flex-direction:column; gap:16px; }
  .flow-heading h1 { font-size:26px; }
  .flow-questions { grid-template-columns:1fr; }
  .flow-questions .flow-editor { display:none; }
  .flow-questions.show-editor .flow-editor { display:block; }
  .flow-questions.show-editor .flow-question-list { display:none; }
  .flow-back { display:inline-flex; margin-bottom:8px; padding:0; }
}
</style>
