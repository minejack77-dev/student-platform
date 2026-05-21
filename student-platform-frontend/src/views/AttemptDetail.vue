<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Answer, Attempt, AttemptQuestion } from "@/api.js";
import { sanitizeInlineRichText } from "@/utils/richText.js";

const props = defineProps(["id"]);
const router = useRouter();

const attempt = ref(null);
const questionList = ref([]);
const selectionsByQuestion = ref({});
const saveStateByQuestion = ref({});
const savingByQuestion = ref({});
const activeQuestionIndex = ref(0);

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
    return "Attempt finished";
  }
  if (attemptInteractionLocked.value) {
    return "Window closed";
  }
  if (activeQuestionSaveState.value === "saving") {
    return "Autosaving...";
  }
  if (activeQuestionSaveState.value === "saved") {
    return "Saved";
  }
  if (activeQuestionSaveState.value === "error") {
    return "Save failed";
  }
  return "No changes yet";
});

const renderRichText = (value) => sanitizeInlineRichText(value || "");

const initializeLocalState = () => {
  const nextSelections = {};
  const nextSaveStates = {};
  const nextSavingState = {};

  for (const attemptQuestion of questionList.value) {
    nextSelections[attemptQuestion.id] = attemptQuestion.answer?.selected_choices ?? [];
    nextSaveStates[attemptQuestion.id] = "";
    nextSavingState[attemptQuestion.id] = false;
  }

  selectionsByQuestion.value = nextSelections;
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
  } catch (error) {
    loadError.value = error?.response?.data?.detail || "Could not load attempt data.";
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

const saveAnswer = async (attemptQuestion) => {
  if (!attemptQuestion || attemptCompleted.value || attemptInteractionLocked.value) {
    return;
  }
  saveError.value = "";

  const attemptQuestionId = attemptQuestion.id;
  savingByQuestion.value = {
    ...savingByQuestion.value,
    [attemptQuestionId]: true,
  };
  saveStateByQuestion.value = {
    ...saveStateByQuestion.value,
    [attemptQuestionId]: "saving",
  };

  try {
    const payload = {
      attempt_question: attemptQuestionId,
      selected_choices: selectedChoicesFor(attemptQuestionId),
    };
    if (attemptQuestion.answer?.id) {
      payload.id = attemptQuestion.answer.id;
    }

    const savedAnswer = await Answer.save(payload);
    attemptQuestion.answer = savedAnswer;
    selectionsByQuestion.value = {
      ...selectionsByQuestion.value,
      [attemptQuestionId]: savedAnswer.selected_choices ?? [],
    };
    saveStateByQuestion.value = {
      ...saveStateByQuestion.value,
      [attemptQuestionId]: "saved",
    };
  } catch (error) {
    saveStateByQuestion.value = {
      ...saveStateByQuestion.value,
      [attemptQuestionId]: "error",
    };
    saveError.value =
      error?.response?.data?.selected_choices?.[0] ||
      error?.response?.data?.attempt_question?.[0] ||
      error?.response?.data?.detail ||
      "Could not autosave answer.";
  } finally {
    savingByQuestion.value = {
      ...savingByQuestion.value,
      [attemptQuestionId]: false,
    };
  }
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
  }
};

const nextQuestion = () => {
  if (!isLastQuestion.value) {
    activeQuestionIndex.value += 1;
  }
};

const completeAttempt = async () => {
  if (
    !attempt.value ||
    attemptCompleted.value ||
    !isLastQuestion.value ||
    attemptInteractionLocked.value ||
    isCompleting.value ||
    hasPendingSaves.value
  ) {
    return;
  }

  completeError.value = "";
  isCompleting.value = true;
  try {
    await Attempt.save({
      id: attempt.value.id,
      status: "completed",
    });
    await loadAttemptData();
  } catch (error) {
    completeError.value = error?.response?.data?.detail || "Could not complete attempt.";
  } finally {
    isCompleting.value = false;
  }
};

const goHome = async () => {
  await router.push({ name: "student-home" });
};

watch(
  () => props.id,
  async () => {
    activeQuestionIndex.value = 0;
    await loadAttemptData();
  },
);

onMounted(async () => {
  await loadAttemptData();
});
</script>

<template>
  <div class="attempt-page">
    <section class="surface-card attempt-hero">
      <div>
        <span class="pill">Attempt</span>
        <h1 class="attempt-title">{{ attempt?.subject_name || "Subject" }}</h1>
        <p class="attempt-topic">{{ attempt?.topic_title || "Topic" }}</p>
      </div>

      <div class="hero-metrics">
        <div class="metric-card">
          <div class="metric-label">Questions</div>
          <div class="metric-value">{{ totalQuestions }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Status</div>
          <div class="metric-status" :class="{ done: attemptCompleted }">
            {{ attemptCompleted ? "Completed" : "In progress" }}
          </div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>
    <div v-if="saveError" class="alert alert-danger">{{ saveError }}</div>
    <div v-if="completeError" class="alert alert-danger">{{ completeError }}</div>
    <div v-if="attemptInteractionLocked" class="alert alert-warning">
      This scheduled test can only be completed on its assigned date. The window is closed.
    </div>

    <section v-if="isLoading" class="surface-card attempt-state">
      Loading attempt...
    </section>

    <section
      v-else-if="totalQuestions === 0 && !attemptCompleted"
      class="surface-card attempt-state"
    >
      No questions were assigned to this attempt.
    </section>

    <section v-else-if="!attemptCompleted" class="surface-card question-panel">
      <div class="panel-head">
        <div class="pill">
          Question {{ activeQuestionIndex + 1 }} / {{ totalQuestions }}
        </div>
        <div class="save-indicator" :class="activeQuestionSaveState">
          {{ activeQuestionSaveLabel }}
        </div>
      </div>

      <h2 class="question-text" v-html="renderRichText(activeQuestion.question.text)" />
      <p
        v-if="activeQuestion.question.instruction"
        class="question-instruction"
        v-html="renderRichText(activeQuestion.question.instruction)"
      />

      <div class="choices-list">
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
            :disabled="attemptCompleted || savingByQuestion[activeQuestion.id]"
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
          Previous question
        </button>

        <button
          class="btn btn-outline-primary"
          type="button"
          :disabled="isLastQuestion"
          @click="nextQuestion"
        >
          Next question
        </button>

        <button
          class="btn btn-primary"
          type="button"
          :disabled="!isLastQuestion || hasPendingSaves || isCompleting || attemptInteractionLocked"
          @click="completeAttempt"
        >
          {{ isCompleting ? "Finishing..." : "Finish attempt" }}
        </button>
      </div>
    </section>

    <section v-if="attemptCompleted" class="surface-card result-panel">
      <div class="result-head">
        <h2 class="section-title">Result</h2>
        <button class="btn btn-primary" type="button" @click="goHome">
          Back to home
        </button>
      </div>
      <div class="attempt-result-badge" :class="attemptOutcome">
        {{ attemptOutcome === "success" ? "Success" : "Fail" }}
        | {{ correctCount }} / {{ totalQuestions }} correct
        | pass from {{ passingScore }}
      </div>
      <div class="result-grid">
        <div class="result-card success">
          <div class="result-label">Correct</div>
          <div class="result-value">{{ correctCount }}</div>
        </div>
        <div class="result-card danger">
          <div class="result-label">Wrong</div>
          <div class="result-value">{{ wrongCount }}</div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped src="./AttemptDetail.css"></style>
