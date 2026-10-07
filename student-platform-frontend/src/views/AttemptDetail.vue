<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { apiError } from "@/utils/apiError";
import { Answer, Attempt, AttemptQuestion } from "@/api.js";
import QuestionImageGallery from "@/components/QuestionImageGallery.vue";
import { sanitizeInlineRichText } from "@/utils/richText.js";

const props = defineProps(["id"]);
const router = useRouter();
const { t } = useI18n();
const auth = useAuthStore();
const teacherView = computed(() => auth.role === 'teacher');
const showSubmitConfirm = ref(false);
const draftKey = () => `attempt-draft:${auth.user?.id}:${props.id}`;
const readDraft = () => { try { return JSON.parse(sessionStorage.getItem(draftKey()) || '{}'); } catch { return {}; } };
const persistAnswerDraft = (question) => {
  if (teacherView.value) return;
  try {
    const draft = readDraft();
    draft[question.id] = { choices: selectedChoicesFor(question.id), matching: matchingSelectionFor(question.id) };
    sessionStorage.setItem(draftKey(), JSON.stringify(draft));
  } catch { /* Storage may be unavailable; the visible save error remains. */ }
};
const clearAnswerDraft = (id) => {
  try { const draft = readDraft(); delete draft[id]; sessionStorage.setItem(draftKey(), JSON.stringify(draft)); } catch { /* optional storage */ }
};

const attempt = ref(null);
const questionList = ref([]);
const selectionsByQuestion = ref({});
const matchingSelectionsByQuestion = ref({});
const activeMatchingLeftByQuestion = ref({});
const saveStateByQuestion = ref({});
const savingByQuestion = ref({});
const activeQuestionIndex = ref(0);
const matchingBoardRef = ref(null);
const matchingItemRefs = ref({});
const matchingLinks = ref([]);
let matchingLinkFrame = null;

const isLoading = ref(false);
const isCompleting = ref(false);
const loadError = ref("");
const saveError = ref("");
const completeError = ref("");

const totalQuestions = computed(() => questionList.value.length);
const activeQuestion = computed(() => questionList.value[activeQuestionIndex.value] ?? null);
const isFirstQuestion = computed(() => activeQuestionIndex.value <= 0);
const isLastQuestion = computed(
  () => activeQuestionIndex.value >= totalQuestions.value - 1,
);
const attemptCompleted = computed(() => attempt.value?.status === "completed");
const reviewMode = computed(() => attemptCompleted.value || teacherView.value);
const hasFailedSaves = computed(() => Object.values(saveStateByQuestion.value).some(state => state === 'error' || state === 'draft'));
const isAnswered = (question) => isMatchingQuestion(question)
  ? Object.keys(matchingSelectionFor(question.id)).length === question.matching_left_items.length
  : selectedChoicesFor(question.id).length > 0;
const answeredCount = computed(() => questionList.value.filter(isAnswered).length);
const questionStatus = (question) => ['error', 'draft'].includes(saveStateByQuestion.value[question.id])
  ? t('ux.saveFailed') : isAnswered(question) ? t('ux.answered') : t('ux.unanswered');
const hasPendingSaves = computed(() => Object.values(savingByQuestion.value).some(Boolean));
const attemptInteractionLocked = computed(
  () => attempt.value?.can_interact_today === false && !attemptCompleted.value,
);

const correctCount = computed(() => {
  if (typeof attempt.value?.correct_count === "number") {
    return attempt.value.correct_count;
  }
  return questionList.value.filter((item) => item.answer?.is_correct === true).length;
});

const wrongCount = computed(() => {
  if (typeof attempt.value?.wrong_count === "number") {
    return attempt.value.wrong_count;
  }
  return totalQuestions.value - correctCount.value;
});

const attemptOutcome = computed(() => attempt.value?.result_outcome || null);
const passingScore = computed(() => attempt.value?.passing_correct_answers ?? 8);

const activeQuestionSaveState = computed(() => {
  if (!activeQuestion.value) {
    return "";
  }
  return saveStateByQuestion.value[activeQuestion.value.id] ?? "";
});

const activeQuestionSaveLabel = computed(() => {
  if (attemptCompleted.value) {
    return t("attemptDetail.finished");
  }
  if (attemptInteractionLocked.value) {
    return t("attemptDetail.windowClosed");
  }
  if (activeQuestionSaveState.value === "saving") {
    return t("attemptDetail.autosaving");
  }
  if (activeQuestionSaveState.value === "saved") {
    return t("attemptDetail.saved");
  }
  if (activeQuestionSaveState.value === "error") {
    return t("attemptDetail.saveFailed");
  }
  if (activeQuestionSaveState.value === 'draft') return t('ux.unsavedDraft');
  return t("attemptDetail.noChangesYet");
});

const renderRichText = (value) => sanitizeInlineRichText(value || "");

const isMatchingQuestion = (attemptQuestion) =>
  attemptQuestion?.question?.question_type === "matching";

const initializeLocalState = () => {
  const draft = !teacherView.value && !attemptCompleted.value ? readDraft() : {};
  const nextSelections = {};
  const nextMatchingSelections = {};
  const nextActiveMatchingLeft = {};
  const nextSaveStates = {};
  const nextSavingState = {};

  for (const attemptQuestion of questionList.value) {
    nextSelections[attemptQuestion.id] = attemptQuestion.answer?.selected_choices ?? [];
    nextMatchingSelections[attemptQuestion.id] =
      attemptQuestion.answer?.selected_matching_pairs ?? {};
    nextActiveMatchingLeft[attemptQuestion.id] = null;
    nextSaveStates[attemptQuestion.id] = attemptQuestion.answer ? "saved" : "";
    if (draft[attemptQuestion.id]) {
      nextSelections[attemptQuestion.id] = draft[attemptQuestion.id].choices ?? [];
      const matchingDraft = draft[attemptQuestion.id].matching ?? {};
      const leftTokens = new Set((attemptQuestion.matching_left_items ?? []).map(item => item.id));
      const rightTokens = new Set((attemptQuestion.matching_right_items ?? []).map(item => item.id));
      if (isMatchingQuestion(attemptQuestion) && Object.entries(matchingDraft).some(([left, right]) => !leftTokens.has(left) || !rightTokens.has(right))) {
        // Old numeric drafts cannot be translated without disclosing answer keys.
        // Keep the saved server answer and explicitly ask the student to redo it.
        saveError.value = t('ux.matchingDraftExpired');
        clearAnswerDraft(attemptQuestion.id);
      } else {
        nextMatchingSelections[attemptQuestion.id] = matchingDraft;
        nextSaveStates[attemptQuestion.id] = 'draft';
      }
    }
    nextSavingState[attemptQuestion.id] = false;
  }

  selectionsByQuestion.value = nextSelections;
  matchingSelectionsByQuestion.value = nextMatchingSelections;
  activeMatchingLeftByQuestion.value = nextActiveMatchingLeft;
  saveStateByQuestion.value = nextSaveStates;
  savingByQuestion.value = nextSavingState;
};

const loadAttemptData = async () => {
  isLoading.value = true;
  loadError.value = "";
  try {
    const [attemptResponse, questionsResponse] = await Promise.all([
      Attempt.get(props.id),
      AttemptQuestion.filter({
        attempt: props.id,
        page_size: 100,
      }),
    ]);

    attempt.value = attemptResponse;
    questionList.value = (questionsResponse.results ?? questionsResponse).sort(
      (a, b) => a.order - b.order,
    );
    initializeLocalState();
    if (activeQuestionIndex.value >= questionList.value.length) {
      activeQuestionIndex.value = 0;
    }
    scheduleMatchingLinkUpdate();
  } catch (error) {
    loadError.value = apiError(error, 'attemptDetail.errors.load');
  } finally {
    isLoading.value = false;
  }
};

const isSingleChoice = (attemptQuestion) =>
  attemptQuestion?.question?.question_type === "single_choice";

const selectedChoicesFor = (attemptQuestionId) =>
  selectionsByQuestion.value[attemptQuestionId] ?? [];

const isChoiceSelected = (attemptQuestionId, choiceId) =>
  selectedChoicesFor(attemptQuestionId).includes(choiceId);

const submittedChoicesFor = (attemptQuestion) =>
  attemptQuestion?.answer?.selected_choices ?? [];

const correctChoiceIdsFor = (attemptQuestion) =>
  attemptQuestion?.correct_choice_ids ?? [];

const isSubmittedChoiceSelected = (attemptQuestion, choiceId) =>
  submittedChoicesFor(attemptQuestion).includes(choiceId);

const isSubmittedChoiceCorrect = (attemptQuestion, choiceId) =>
  correctChoiceIdsFor(attemptQuestion).includes(choiceId);

const matchingSelectionFor = (attemptQuestionId) =>
  matchingSelectionsByQuestion.value[attemptQuestionId] ?? {};

const submittedMatchingSelectionFor = (attemptQuestion) =>
  attemptQuestion?.answer?.selected_matching_pairs ?? {};

const correctMatchingSelectionFor = (attemptQuestion) =>
  attemptQuestion?.correct_matching_pairs ?? {};

const hasSubmittedAnswer = (attemptQuestion) => {
  if (isMatchingQuestion(attemptQuestion)) {
    return Object.keys(submittedMatchingSelectionFor(attemptQuestion)).length > 0;
  }
  return submittedChoicesFor(attemptQuestion).length > 0;
};

const activeMatchingLeftFor = (attemptQuestionId) =>
  activeMatchingLeftByQuestion.value[attemptQuestionId] ?? null;

const isMatchingLeftActive = (attemptQuestionId, pairId) =>
  activeMatchingLeftFor(attemptQuestionId) === pairId;

const isMatchingLeftPaired = (attemptQuestionId, pairId) =>
  Object.prototype.hasOwnProperty.call(matchingSelectionFor(attemptQuestionId), String(pairId));

const isMatchingRightPaired = (attemptQuestionId, pairId) =>
  Object.values(matchingSelectionFor(attemptQuestionId)).some(
    (value) => String(value) === String(pairId),
  );

const findMatchingItem = (items, itemId) =>
  items.find((item) => String(item.id) === String(itemId));

const setMatchingItemRef = (side, id, element) => {
  const key = `${side}-${id}`;
  if (element) {
    matchingItemRefs.value[key] = element;
  } else {
    delete matchingItemRefs.value[key];
  }
  scheduleMatchingLinkUpdate();
};

const updateMatchingLinks = () => {
  const board = matchingBoardRef.value;
  const attemptQuestion = activeQuestion.value;
  if (!board || !attemptQuestion || !isMatchingQuestion(attemptQuestion)) {
    matchingLinks.value = [];
    return;
  }

  const boardRect = board.getBoundingClientRect();
  const links = [];
  const selection = matchingSelectionFor(attemptQuestion.id);
  for (const [leftId, rightId] of Object.entries(selection)) {
    const leftElement = matchingItemRefs.value[`left-${leftId}`];
    const rightElement = matchingItemRefs.value[`right-${rightId}`];
    if (!leftElement || !rightElement) {
      continue;
    }
    const leftRect = leftElement.getBoundingClientRect();
    const rightRect = rightElement.getBoundingClientRect();
    links.push({
      key: `${leftId}-${rightId}`,
      x1: leftRect.right - boardRect.left,
      y1: leftRect.top + leftRect.height / 2 - boardRect.top,
      x2: rightRect.left - boardRect.left,
      y2: rightRect.top + rightRect.height / 2 - boardRect.top,
    });
  }
  matchingLinks.value = links;
};

const scheduleMatchingLinkUpdate = async () => {
  await nextTick();
  if (typeof window === "undefined") {
    updateMatchingLinks();
    return;
  }
  if (matchingLinkFrame) {
    window.cancelAnimationFrame(matchingLinkFrame);
  }
  matchingLinkFrame = window.requestAnimationFrame(() => {
    matchingLinkFrame = null;
    updateMatchingLinks();
  });
};

const activeMatchingLinkSignature = computed(() => {
  const attemptQuestion = activeQuestion.value;
  if (!attemptQuestion || !isMatchingQuestion(attemptQuestion)) {
    return "";
  }
  const selection = matchingSelectionFor(attemptQuestion.id);
  return [
    attemptQuestion.id,
    attemptQuestion.matching_left_items?.map((item) => item.id).join(",") ?? "",
    attemptQuestion.matching_right_items?.map((item) => item.id).join(",") ?? "",
    Object.entries(selection)
      .map(([leftId, rightId]) => `${leftId}:${rightId}`)
      .sort()
      .join(","),
  ].join("|");
});

const reviewStatusTone = (attemptQuestion) => {
  if (attemptQuestion?.answer?.is_correct === true) {
    return "success";
  }
  if (!hasSubmittedAnswer(attemptQuestion)) {
    return "neutral";
  }
  return "danger";
};

const reviewStatusLabel = (attemptQuestion) => {
  if (attemptQuestion?.answer?.is_correct === true) {
    return t("attemptDetail.reviewStatus.correct");
  }
  if (!hasSubmittedAnswer(attemptQuestion)) {
    return t("attemptDetail.reviewStatus.noAnswer");
  }
  return t("attemptDetail.reviewStatus.wrong");
};

const saveAnswer = async (attemptQuestion) => {
  if (!attemptQuestion || teacherView.value || attemptCompleted.value || attemptInteractionLocked.value) {
    return;
  }
  saveError.value = "";

  const attemptQuestionId = attemptQuestion.id;
  persistAnswerDraft(attemptQuestion);
  savingByQuestion.value = {
    ...savingByQuestion.value,
    [attemptQuestionId]: true,
  };
  saveStateByQuestion.value = {
    ...saveStateByQuestion.value,
    [attemptQuestionId]: "saving",
  };

  try {
    const payload = isMatchingQuestion(attemptQuestion)
      ? {
          attempt_question: attemptQuestionId,
          selected_matching_pairs: matchingSelectionFor(attemptQuestionId),
        }
      : {
          attempt_question: attemptQuestionId,
          selected_choices: selectedChoicesFor(attemptQuestionId),
        };
    if (attemptQuestion.answer?.id) {
      payload.id = attemptQuestion.answer.id;
    }

    const savedAnswer = await Answer.save(payload);
    clearAnswerDraft(attemptQuestionId);
    attemptQuestion.answer = savedAnswer;
    if (isMatchingQuestion(attemptQuestion)) {
      matchingSelectionsByQuestion.value = {
        ...matchingSelectionsByQuestion.value,
        [attemptQuestionId]: savedAnswer.selected_matching_pairs ?? {},
      };
      await scheduleMatchingLinkUpdate();
    } else {
      selectionsByQuestion.value = {
        ...selectionsByQuestion.value,
        [attemptQuestionId]: savedAnswer.selected_choices ?? [],
      };
    }
    saveStateByQuestion.value = {
      ...saveStateByQuestion.value,
      [attemptQuestionId]: "saved",
    };
  } catch (error) {
    saveStateByQuestion.value = {
      ...saveStateByQuestion.value,
      [attemptQuestionId]: "error",
    };
    saveError.value = apiError(error, 'attemptDetail.errors.autosave');
  } finally {
    savingByQuestion.value = {
      ...savingByQuestion.value,
      [attemptQuestionId]: false,
    };
  }
};

const handleMatchingLeftClick = async (attemptQuestion, pairId) => {
  if (!attemptQuestion || attemptCompleted.value || attemptInteractionLocked.value) {
    return;
  }

  const currentActive = activeMatchingLeftFor(attemptQuestion.id);
  activeMatchingLeftByQuestion.value = {
    ...activeMatchingLeftByQuestion.value,
    [attemptQuestion.id]: currentActive === pairId ? null : pairId,
  };
};

const handleMatchingRightClick = async (attemptQuestion, pairId) => {
  if (!attemptQuestion || attemptCompleted.value || attemptInteractionLocked.value) {
    return;
  }

  const leftId = activeMatchingLeftFor(attemptQuestion.id);
  if (!leftId) {
    return;
  }

  const nextSelection = { ...matchingSelectionFor(attemptQuestion.id) };
  for (const existingLeftId of Object.keys(nextSelection)) {
    if (String(nextSelection[existingLeftId]) === String(pairId)) {
      delete nextSelection[existingLeftId];
    }
  }
  nextSelection[String(leftId)] = pairId;

  matchingSelectionsByQuestion.value = {
    ...matchingSelectionsByQuestion.value,
    [attemptQuestion.id]: nextSelection,
  };
  activeMatchingLeftByQuestion.value = {
    ...activeMatchingLeftByQuestion.value,
    [attemptQuestion.id]: null,
  };
  await scheduleMatchingLinkUpdate();
  await saveAnswer(attemptQuestion);
};

const handleChoiceChange = async (attemptQuestion, choiceId, checked) => {
  if (!attemptQuestion || attemptCompleted.value || attemptInteractionLocked.value) {
    return;
  }

  const selected = new Set(selectedChoicesFor(attemptQuestion.id));
  if (isSingleChoice(attemptQuestion)) {
    selected.clear();
    if (checked) {
      selected.add(choiceId);
    }
  } else if (checked) {
    selected.add(choiceId);
  } else {
    selected.delete(choiceId);
  }

  selectionsByQuestion.value = {
    ...selectionsByQuestion.value,
    [attemptQuestion.id]: Array.from(selected),
  };
  await saveAnswer(attemptQuestion);
};

const previousQuestion = () => {
  if (!isFirstQuestion.value) {
    activeQuestionIndex.value -= 1;
    scheduleMatchingLinkUpdate();
  }
};

const nextQuestion = () => {
  if (!isLastQuestion.value) {
    activeQuestionIndex.value += 1;
    scheduleMatchingLinkUpdate();
  }
};

const completeAttempt = async () => {
  if (
    !attempt.value ||
    attemptCompleted.value ||
    teacherView.value ||
    hasFailedSaves.value ||
    attemptInteractionLocked.value ||
    isCompleting.value ||
    hasPendingSaves.value
  ) {
    return;
  }

  completeError.value = "";
  showSubmitConfirm.value = false;
  isCompleting.value = true;
  try {
    await Attempt.submit(attempt.value.id, {
      answers: questionList.value.map(q => isMatchingQuestion(q)
        ? { attempt_question: q.id, selected_matching_pairs: matchingSelectionFor(q.id) }
        : { attempt_question: q.id, selected_choices: selectedChoicesFor(q.id) }),
      confirm_unanswered: answeredCount.value < totalQuestions.value,
    });
    try { sessionStorage.removeItem(draftKey()); } catch { /* optional storage */ }
    saveError.value = '';
    await loadAttemptData();
  } catch (error) {
    completeError.value = apiError(error, 'attemptDetail.errors.complete');
  } finally {
    isCompleting.value = false;
  }
};

const goHome = async () => {
  await router.push(teacherView.value
    ? { name: 'group-overview', params: { id: attempt.value.schedule_group_id }, query: { tab: 'results' } }
    : { name: 'student-home' });
};

const retryAnswers = async () => {
  for (const question of questionList.value) {
    if (['error', 'draft'].includes(saveStateByQuestion.value[question.id])) await saveAnswer(question);
  }
};

watch(
  () => props.id,
  async () => {
    activeQuestionIndex.value = 0;
    await loadAttemptData();
  },
);

watch(activeMatchingLinkSignature, () => {
  scheduleMatchingLinkUpdate();
});

onMounted(async () => {
  window.addEventListener("resize", updateMatchingLinks);
  await loadAttemptData();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateMatchingLinks);
  if (matchingLinkFrame) {
    window.cancelAnimationFrame(matchingLinkFrame);
    matchingLinkFrame = null;
  }
});
</script>

<template>
  <div class="attempt-page">
    <header class="attempt-heading">
      <div>
        <h1 class="attempt-title">{{ attempt?.task_title || attempt?.topic_title || t("common.lesson") }}</h1>
        <p class="attempt-topic">{{ attempt?.subject_name }} / {{ attempt?.topic_title }}</p>
        <p v-if="teacherView">{{ t('ux.teacherReview', { student: attempt?.student_username }) }} · {{ attempt?.schedule_group_name }} · {{ attempt?.schedule_date }}</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <div class="metric-label">{{ t("common.questions") }}</div>
          <div class="metric-value">{{ isLoading || loadError ? '—' : totalQuestions }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">{{ t("common.status") }}</div>
          <div class="metric-status" :class="{ done: attemptCompleted }">
            {{ isLoading || loadError ? '—' : attemptCompleted ? t("attemptDetail.completed") : t("attemptDetail.inProgress") }}
          </div>
        </div>
      </div>
    </header>

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError }} <button class="btn btn-outline-primary" @click="loadAttemptData">{{ t('ux.retry') }}</button></div>
    <div v-if="hasFailedSaves && !reviewMode" class="alert alert-danger" role="alert">
      {{ saveError || t('ux.savingBlocked') }}
      <button class="btn btn-outline-primary" :disabled="hasPendingSaves" @click="retryAnswers">{{ t('ux.saveRetry') }}</button>
    </div>
    <div v-if="completeError" class="alert alert-danger" role="alert">{{ completeError }}</div>
    <div v-if="attemptInteractionLocked" class="alert alert-warning">
      {{ t("attemptDetail.scheduledWindowClosed") }}
    </div>

    <section v-if="isLoading" class="surface-card attempt-state" role="status">
      {{ t("attemptDetail.loadingAttempt") }}
    </section>

    <section
      v-else-if="!loadError && totalQuestions === 0 && !reviewMode"
      class="surface-card attempt-state"
    >
      {{ t("attemptDetail.noQuestionsAssigned") }}
    </section>

    <section v-else-if="!loadError && !reviewMode" class="surface-card question-panel">
      <nav class="question-navigation" :aria-label="t('ux.questionsNav')">
        <button v-for="(question, index) in questionList" :key="question.id" class="btn btn-outline-primary"
          :class="{ active: index === activeQuestionIndex, 'border-danger': ['error', 'draft'].includes(saveStateByQuestion[question.id]) }"
          :aria-current="index === activeQuestionIndex ? 'step' : undefined"
          :aria-label="`${index + 1}: ${questionStatus(question)}`" @click="activeQuestionIndex = index">
          {{ index + 1 }} · {{ questionStatus(question) }}
        </button>
      </nav>
      <div class="panel-head">
        <div class="pill">
          {{ t("attemptDetail.saveIndicator.questionCounter", { current: activeQuestionIndex + 1, total: totalQuestions }) }}
        </div>
        <div class="save-indicator" :class="activeQuestionSaveState" role="status" aria-live="polite">
          {{ activeQuestionSaveLabel }}
        </div>
      </div>

      <h2 class="question-text" v-html="renderRichText(activeQuestion.question.text)" />
      <p
        v-if="activeQuestion.question.instruction"
        class="question-instruction"
        v-html="renderRichText(activeQuestion.question.instruction)"
      />

      <QuestionImageGallery
        v-if="activeQuestion.question.images?.length"
        :images="activeQuestion.question.images"
      />

      <div v-if="isMatchingQuestion(activeQuestion)" class="matching-help">
        <p>{{ t('ux.matchingHelp') }}</p>
        <p role="status">{{ t('ux.matchingProgress', { count: Object.keys(matchingSelectionFor(activeQuestion.id)).length, total: activeQuestion.matching_left_items.length }) }}</p>
        <button class="btn btn-outline-primary btn-sm" :disabled="hasPendingSaves || attemptInteractionLocked" @click="matchingSelectionsByQuestion[activeQuestion.id] = {}; saveAnswer(activeQuestion)">{{ t('ux.clearPairs') }}</button>
      </div>
      <div v-if="isMatchingQuestion(activeQuestion)" ref="matchingBoardRef" class="matching-board">
        <svg class="matching-lines" aria-hidden="true">
          <line
            v-for="link in matchingLinks"
            :key="link.key"
            :x1="link.x1"
            :y1="link.y1"
            :x2="link.x2"
            :y2="link.y2"
          />
        </svg>

        <div class="matching-column">
          <button
            v-for="item in activeQuestion.matching_left_items"
            :key="item.id"
            :ref="(element) => setMatchingItemRef('left', item.id, element)"
            class="matching-item matching-left"
            :class="{
              active: isMatchingLeftActive(activeQuestion.id, item.id),
              paired: isMatchingLeftPaired(activeQuestion.id, item.id),
            }"
            type="button"
            :aria-pressed="isMatchingLeftActive(activeQuestion.id, item.id)"
            :disabled="attemptInteractionLocked || savingByQuestion[activeQuestion.id] || isCompleting"
            @click="handleMatchingLeftClick(activeQuestion, item.id)"
          >
            <span v-html="renderRichText(item.content)" />
          </button>
        </div>

        <div class="matching-column">
          <button
            v-for="item in activeQuestion.matching_right_items"
            :key="item.id"
            :ref="(element) => setMatchingItemRef('right', item.id, element)"
            class="matching-item matching-right"
            :class="{ paired: isMatchingRightPaired(activeQuestion.id, item.id) }"
            type="button"
            :disabled="attemptInteractionLocked || savingByQuestion[activeQuestion.id] || isCompleting"
            @click="handleMatchingRightClick(activeQuestion, item.id)"
          >
            <span v-html="renderRichText(item.content)" />
          </button>
        </div>
      </div>

      <div v-else class="choices-list">
        <label
          v-for="choice in activeQuestion.question.choices"
          :key="choice.id"
          class="choice-item"
          :class="{ selected: isChoiceSelected(activeQuestion.id, choice.id) }"
        >
          <input
            :type="isSingleChoice(activeQuestion) ? 'radio' : 'checkbox'"
            :name="`question-${activeQuestion.id}`"
            :checked="isChoiceSelected(activeQuestion.id, choice.id)"
            :disabled="attemptInteractionLocked || savingByQuestion[activeQuestion.id] || isCompleting"
            @change="handleChoiceChange(activeQuestion, choice.id, $event.target.checked)"
          />
          <span v-html="renderRichText(choice.text)" />
        </label>
      </div>

      <div class="panel-actions">
        <button
          class="btn btn-outline-primary"
          type="button"
          :disabled="isFirstQuestion"
          @click="previousQuestion"
        >
          {{ t("attemptDetail.previousQuestion") }}
        </button>

        <button
          class="btn btn-outline-primary"
          type="button"
          :disabled="isLastQuestion"
          @click="nextQuestion"
        >
          {{ t("attemptDetail.nextQuestion") }}
        </button>

        <button
          class="btn btn-primary"
          type="button"
          :disabled="hasFailedSaves || hasPendingSaves || isCompleting || attemptInteractionLocked"
          @click="showSubmitConfirm = true"
        >
          {{ isCompleting ? t("attemptDetail.finishing") : t("attemptDetail.finishAttempt") }}
        </button>
      </div>
    </section>

    <ConfirmDialog v-if="showSubmitConfirm" :title="t('ux.finishTitle')"
      :message="t('ux.finishSummary', { answered: answeredCount, total: totalQuestions, missing: totalQuestions - answeredCount })"
      :confirm-label="t('ux.submit')" :cancel-label="t('ux.cancel')" @confirm="completeAttempt" @cancel="showSubmitConfirm = false" />
    <section v-if="reviewMode && !loadError" class="surface-card result-panel">
      <div class="result-head">
        <h2 class="section-title">{{ t("attemptDetail.result") }}</h2>
        <button class="btn btn-primary" type="button" @click="goHome">
          {{ teacherView ? t('ux.backResults') : t("attemptDetail.backHome") }}
        </button>
      </div>
      <div v-if="attemptCompleted" class="attempt-result-badge" :class="attemptOutcome">
        {{ attemptOutcome === "success" ? t("attemptDetail.success") : t("attemptDetail.fail") }}
        | {{ t("attemptDetail.correctSummary", { count: correctCount, total: totalQuestions }) }}
        | {{ t("attemptDetail.passFromLabel", { count: passingScore }) }}
      </div>
      <div class="result-grid">
        <div class="result-card success">
          <div class="result-label">{{ t("attemptDetail.correct") }}</div>
          <div class="result-value">{{ correctCount }}</div>
        </div>
        <div class="result-card danger">
          <div class="result-label">{{ t("attemptDetail.wrong") }}</div>
          <div class="result-value">{{ wrongCount }}</div>
        </div>
      </div>

      <div class="result-review">
        <div class="review-head">
          <h3 class="review-title">{{ t("attemptDetail.answerReview") }}</h3>
          <p class="review-subtitle">
            {{ t("attemptDetail.answerReviewSubtitle") }}
          </p>
        </div>

        <div v-if="questionList.length" class="review-list">
          <article
            v-for="attemptQuestion in questionList"
            :key="attemptQuestion.id"
            class="review-question"
            :class="reviewStatusTone(attemptQuestion)"
          >
            <div class="review-question-head">
              <span class="pill">{{ t("attemptDetail.questionNumber", { order: attemptQuestion.order }) }}</span>
              <span class="review-status" :class="reviewStatusTone(attemptQuestion)">
                {{ reviewStatusLabel(attemptQuestion) }}
              </span>
            </div>

            <h3
              class="review-question-text"
              v-html="renderRichText(attemptQuestion.question.text)"
            />
            <p
              v-if="attemptQuestion.question.instruction"
              class="question-instruction"
              v-html="renderRichText(attemptQuestion.question.instruction)"
            />
            <QuestionImageGallery
              v-if="attemptQuestion.question.images?.length"
              :images="attemptQuestion.question.images"
              compact
            />
            <p
              v-if="
                isMatchingQuestion(attemptQuestion)
                  ? Object.keys(submittedMatchingSelectionFor(attemptQuestion)).length === 0
                  : submittedChoicesFor(attemptQuestion).length === 0
              "
              class="review-empty"
            >
              {{ t("attemptDetail.noAnswerSelected") }}
            </p>

            <div v-if="isMatchingQuestion(attemptQuestion)" class="review-matching-list">
              <div
                v-for="leftItem in attemptQuestion.matching_left_items"
                :key="leftItem.id"
                class="review-matching-row"
                :class="{
                  correct:
                    String(submittedMatchingSelectionFor(attemptQuestion)[leftItem.id]) ===
                    String(correctMatchingSelectionFor(attemptQuestion)[leftItem.id]),
                  wrong:
                    submittedMatchingSelectionFor(attemptQuestion)[leftItem.id] &&
                    String(submittedMatchingSelectionFor(attemptQuestion)[leftItem.id]) !==
                      String(correctMatchingSelectionFor(attemptQuestion)[leftItem.id]),
                }"
              >
                <div class="review-matching-side" v-html="renderRichText(leftItem.content)" />
                <div class="review-matching-arrow">&rarr;</div>
                <div class="review-matching-side">
                  <div
                    v-if="findMatchingItem(attemptQuestion.matching_right_items, submittedMatchingSelectionFor(attemptQuestion)[leftItem.id])"
                    v-html="
                      renderRichText(
                        findMatchingItem(
                          attemptQuestion.matching_right_items,
                          submittedMatchingSelectionFor(attemptQuestion)[leftItem.id],
                        ).content,
                      )
                    "
                  />
                  <span v-else class="review-empty">{{ t("attemptDetail.noAnswerSelected") }}</span>
                  <div
                    v-if="
                      String(submittedMatchingSelectionFor(attemptQuestion)[leftItem.id]) !==
                      String(correctMatchingSelectionFor(attemptQuestion)[leftItem.id])
                    "
                    class="review-correct-match"
                  >
                    <span class="review-tag correct">{{ t("attemptDetail.correctAnswer") }}</span>
                    <span
                      v-html="
                        renderRichText(
                          findMatchingItem(
                            attemptQuestion.matching_right_items,
                            correctMatchingSelectionFor(attemptQuestion)[leftItem.id],
                          )?.content || '',
                        )
                      "
                    />
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="review-choices">
              <div
                v-for="choice in attemptQuestion.question.choices"
                :key="choice.id"
                class="review-choice"
                :class="{
                  selected: isSubmittedChoiceSelected(attemptQuestion, choice.id),
                  correct: isSubmittedChoiceCorrect(attemptQuestion, choice.id),
                  'selected-correct':
                    isSubmittedChoiceSelected(attemptQuestion, choice.id) &&
                    isSubmittedChoiceCorrect(attemptQuestion, choice.id),
                  'selected-wrong':
                    isSubmittedChoiceSelected(attemptQuestion, choice.id) &&
                    !isSubmittedChoiceCorrect(attemptQuestion, choice.id),
                  'missed-correct':
                    !isSubmittedChoiceSelected(attemptQuestion, choice.id) &&
                    isSubmittedChoiceCorrect(attemptQuestion, choice.id),
                }"
              >
                <div class="review-choice-main">
                  <span class="review-choice-order">{{ choice.order }}</span>
                  <span v-html="renderRichText(choice.text)" />
                </div>

                <div class="review-choice-tags">
                  <span
                    v-if="isSubmittedChoiceSelected(attemptQuestion, choice.id)"
                    class="review-tag selected"
                  >
                    {{ t("attemptDetail.selected") }}
                  </span>
                  <span
                    v-if="isSubmittedChoiceCorrect(attemptQuestion, choice.id)"
                    class="review-tag correct"
                  >
                    {{ t("attemptDetail.correctAnswer") }}
                  </span>
                </div>
              </div>
            </div>
          </article>
        </div>

        <p v-else class="review-empty">{{ t("attemptDetail.noQuestionsForReview") }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped src="./AttemptDetail.css"></style>
