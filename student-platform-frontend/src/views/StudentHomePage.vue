<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import axios from "axios";

import { Attempt, Group, Student, subscribeToPush } from "@/api.js";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

const WEEK_LENGTH = 7;
const RECENT_RESULTS_LIMIT = 3;
const DAY_NAME_FORMAT = { weekday: "short" };
const DAY_NUMBER_FORMAT = { day: "numeric" };
const MONTH_DAY_FORMAT = { month: "short", day: "numeric" };
const RESULT_DATE_FORMAT = { month: "short", day: "numeric", year: "numeric" };
const MONTH_RANGE_FORMAT = { month: "long", year: "numeric" };

const { t } = useI18n();
const { formatWithLocale } = useLocaleFormatting();

const formatISODate = (date) => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseISODate = (value) => {
  const [year, month, day] = (value || "").split("-").map(Number);
  if (!year || !month || !day) {
    return null;
  }
  return new Date(year, month - 1, day);
};

const startOfWeek = (date) => {
  const value = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const day = value.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  value.setDate(value.getDate() + diff);
  return value;
};

const shiftDateByDays = (value, days) => {
  const next = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  next.setDate(next.getDate() + days);
  return next;
};

const router = useRouter();

const statsItems = ref([]);
const statsLoading = ref(false);

const loadStats = async () => {
  statsLoading.value = true;
  try {
    const response = await Student.getAllAssignments();
    statsItems.value = response.results ?? [];
  } catch {
    statsItems.value = [];
  } finally {
    statsLoading.value = false;
  }
};

const today = formatISODate(new Date());

const getItemState = (item) => {
  if (item.attempt_status === "completed") {
    return item.result_outcome === "success" ? "success" : "fail";
  }
  if (item.attempt_status === "in_progress") {
    return item.date === today ? "in_progress" : "expired";
  }
  if (!item.date || item.date < today) {
    return "missed";
  }
  if (item.date > today) {
    return "upcoming";
  }
  return "available";
};

const completedItems = computed(() =>
  statsItems.value.filter((item) => item.attempt_status === "completed"),
);
const missedItems = computed(() =>
  statsItems.value.filter((item) => getItemState(item) === "missed"),
);
const completedCount = computed(() => completedItems.value.length + missedItems.value.length);
const passedCount = computed(
  () => completedItems.value.filter((item) => item.result_outcome === "success").length,
);
const recentResultItems = computed(() =>
  [...statsItems.value]
    .filter((item) => item.attempt_status === "completed" && item.attempt_id)
    .sort((left, right) => {
      const leftDate = left.date || "";
      const rightDate = right.date || "";
      if (leftDate !== rightDate) {
        return rightDate.localeCompare(leftDate);
      }
      return (right.attempt_id ?? 0) - (left.attempt_id ?? 0);
    })
    .slice(0, RECENT_RESULTS_LIMIT),
);

const rankingData = ref(null);
const rankingLoading = ref(false);

const loadRanking = async () => {
  const groupId = statsItems.value[0]?.group_id;
  if (!groupId) {
    return;
  }
  rankingLoading.value = true;
  try {
    rankingData.value = await Group.getRanking(groupId);
  } catch {
    rankingData.value = null;
  } finally {
    rankingLoading.value = false;
  }
};

const myRank = computed(() => {
  if (!rankingData.value || !rankingData.value.rank) {
    return null;
  }
  return { rank: rankingData.value.rank, total: rankingData.value.total };
});

const calendarStartDate = ref(formatISODate(startOfWeek(new Date())));
const calendarDays = ref([]);
const searchQuery = ref("");
const loadError = ref("");
const actionError = ref("");
const isLoading = ref(false);
const startingTaskKey = ref("");

const enrichCalendarResponse = (response) => {
  const results = response.results ?? [];
  return results.map((day) => ({
    ...day,
    items: (day.items ?? []).map((item, index) => ({
      ...item,
      task_key: `${day.date}-${item.group_id}-${item.task_id || item.topic_id}-${item.teacher_id}-${index}`,
    })),
  }));
};

const loadSchedule = async () => {
  isLoading.value = true;
  loadError.value = "";
  actionError.value = "";
  try {
    const response = await Student.getScheduledAssignments({
      start_date: calendarStartDate.value,
      days: WEEK_LENGTH,
    });
    calendarDays.value = enrichCalendarResponse(response);
  } catch (error) {
    loadError.value =
      error?.response?.data?.detail || t("studentHome.loadError");
    calendarDays.value = [];
  } finally {
    isLoading.value = false;
  }
};

const shiftCalendarWeek = async (direction) => {
  const nextStartDate = shiftDateByDays(
    parseISODate(calendarStartDate.value),
    direction * WEEK_LENGTH,
  );
  calendarStartDate.value = formatISODate(nextStartDate);
  await loadSchedule();
};

const jumpToCurrentWeek = async () => {
  calendarStartDate.value = formatISODate(startOfWeek(new Date()));
  await loadSchedule();
};

const startTask = async (task) => {
  actionError.value = "";
  startingTaskKey.value = task.task_key;
  try {
    if (task.attempt_id && task.attempt_status === "in_progress") {
      await router.push({
        name: "attempt-detail",
        params: { id: task.attempt_id },
      });
      return;
    }

    const createdAttempt = await Attempt.save({
      schedule_entry: task.schedule_entry_id,
      subject: task.subject_id,
    });
    await router.push({
      name: "attempt-detail",
      params: { id: createdAttempt.id },
    });
  } catch (error) {
    actionError.value =
      getApiErrorMessage(error?.response?.data) || t("studentHome.startTaskError");
  } finally {
    startingTaskKey.value = "";
  }
};

const openAttemptResult = async (attemptId) => {
  if (!attemptId) {
    return;
  }
  await router.push({
    name: "attempt-detail",
    params: { id: attemptId },
  });
};

const getApiErrorMessage = (data) => {
  if (!data) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }

  const fields = [
    "detail",
    "task",
    "schedule_entry",
    "topic",
    "subject",
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

const compareToToday = (value) => {
  const current = formatISODate(new Date());
  if (value === current) {
    return 0;
  }
  return value < current ? -1 : 1;
};

const getTaskState = (task, date) => {
  if (task.attempt_status === "completed") {
    return task.result_outcome === "success" ? "success" : "fail";
  }
  if (task.attempt_status === "in_progress") {
    return compareToToday(date) === 0 ? "in_progress" : "expired";
  }
  if ((task.active_question_count ?? 0) < (task.required_question_count ?? 10)) {
    return "not_ready";
  }
  const relation = compareToToday(date);
  if (relation < 0) {
    return "missed";
  }
  if (relation > 0) {
    return "upcoming";
  }
  return "available";
};

const getTaskStateLabel = (task, date) => {
  const state = getTaskState(task, date);
  if (state === "success") {
    return t("studentHome.taskState.success");
  }
  if (state === "fail") {
    return t("studentHome.taskState.fail");
  }
  if (state === "in_progress") {
    return t("studentHome.taskState.inProgress");
  }
  if (state === "expired") {
    return t("studentHome.taskState.expired");
  }
  if (state === "missed") {
    return t("studentHome.taskState.missed");
  }
  if (state === "upcoming") {
    return t("studentHome.taskState.locked");
  }
  if (state === "not_ready") {
    return t("studentHome.taskState.notReady");
  }
  return t("studentHome.taskState.available");
};

const getTaskStateCopy = (task, date) => {
  const state = getTaskState(task, date);
  if (state === "success" || state === "fail") {
    return t("studentHome.taskCopy.score", {
      correct: task.correct_count ?? 0,
      total: task.total_questions ?? 0,
    });
  }
  if (state === "in_progress") {
    return t("studentHome.taskCopy.continue");
  }
  if (state === "expired") {
    return t("studentHome.taskCopy.expired");
  }
  if (state === "missed") {
    return t("studentHome.taskCopy.missed");
  }
  if (state === "upcoming") {
    return t("studentHome.taskCopy.availableOn", {
      date: formatWithLocale(parseISODate(date), MONTH_DAY_FORMAT),
    });
  }
  if (state === "not_ready") {
    return t("studentHome.taskCopy.notReady", {
      active: task.active_question_count ?? 0,
      required: task.required_question_count ?? 10,
    });
  }
  return t("studentHome.taskCopy.availableToday");
};

const getTaskButtonLabel = (task, date) => {
  const state = getTaskState(task, date);
  if (state === "in_progress") {
    return t("studentHome.taskButton.continue");
  }
  if (state === "available") {
    return t("studentHome.taskButton.start");
  }
  return t("studentHome.taskButton.unavailable");
};

const canStartOrContinueTask = (task, date) => {
  const state = getTaskState(task, date);
  return state === "available" || state === "in_progress";
};

const filteredCalendarDays = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) {
    return calendarDays.value;
  }

  return calendarDays.value.map((day) => ({
    ...day,
    items: day.items.filter((task) =>
      [task.task_title, task.topic_title, task.group_name, task.teacher_username, task.subject_name]
        .map((value) => (value || "").toLowerCase())
        .some((value) => value.includes(query)),
    ),
  }));
});

const filteredTaskCount = computed(() =>
  filteredCalendarDays.value.reduce((sum, day) => sum + day.items.length, 0),
);
const calendarRangeLabel = computed(() => {
  if (calendarDays.value.length === 0) {
    return "";
  }
  const first = parseISODate(calendarDays.value[0].date);
  const last = parseISODate(calendarDays.value[calendarDays.value.length - 1].date);
  if (!first || !last) {
    return "";
  }
  return `${formatWithLocale(first, MONTH_RANGE_FORMAT)} - ${formatWithLocale(first, MONTH_DAY_FORMAT)} - ${formatWithLocale(last, MONTH_DAY_FORMAT)}`;
});

const isToday = (value) => formatISODate(new Date()) === value;
const isWeekend = (value) => {
  const date = parseISODate(value);
  const day = date?.getDay();
  return day === 0 || day === 6;
};
const formatDayName = (value) => formatWithLocale(parseISODate(value), DAY_NAME_FORMAT);
const formatDayNumber = (value) => formatWithLocale(parseISODate(value), DAY_NUMBER_FORMAT);
const formatMonthDay = (value) => formatWithLocale(parseISODate(value), MONTH_DAY_FORMAT);
const formatResultDate = (value) => {
  const date = parseISODate(value);
  return date ? formatWithLocale(date, RESULT_DATE_FORMAT) : value || t("common.unknownDate");
};
const getRecentResultTitle = (item) =>
  item.task_title || item.topic_title || t("studentHome.recentResultTitleFallback");

const pushStatus = ref("Notification" in window ? Notification.permission : "unsupported");
const testNotifLoading = ref(false);
const testNotifCountdown = ref(0);
const testNotifMessage = ref("");

const pushError = ref("");
const pushSuccess = ref("");

const enablePush = async () => {
  pushError.value = "";
  testNotifMessage.value = "";
  pushSuccess.value = "";
  try {
    await subscribeToPush();
    pushStatus.value = Notification.permission;
    pushSuccess.value = t("studentHome.notifications.enabled");
  } catch (error) {
    if (Notification.permission === "denied") {
      pushError.value = t("studentHome.notifications.blocked");
    } else {
      pushError.value = t("studentHome.notifications.enableFailed", {
        message: error.message,
      });
    }
  }
};

const sendTestNotification = async () => {
  testNotifLoading.value = true;
  testNotifMessage.value = "";
  pushSuccess.value = "";
  try {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
    await axios.post("/api/push/test/", {}, {
      headers: { "X-CSRFToken": csrf },
    });
    testNotifMessage.value = t("studentHome.notificationSent");
  } catch {
    testNotifMessage.value = t("studentHome.notificationFailed");
  } finally {
    testNotifCountdown.value = 10;
    const interval = setInterval(() => {
      testNotifCountdown.value -= 1;
      if (testNotifCountdown.value <= 0) {
        clearInterval(interval);
        testNotifLoading.value = false;
      }
    }, 1000);
  }
};

onMounted(async () => {
  await Promise.all([loadSchedule(), loadStats()]);
  await loadRanking();
});
</script>

<template>
  <div class="student-page">
    <section class="surface-card hero-panel">
      <div class="hero-copy">
        <span class="pill">{{ t("studentHome.badge") }}</span>
        <h1 class="hero-title">{{ t("studentHome.title") }}</h1>
        <p class="hero-subtitle">{{ t("studentHome.subtitle") }}</p>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>
    <div v-if="actionError" class="alert alert-danger">{{ actionError }}</div>

    <section class="surface-card section-card">
      <div class="schedule-header">
        <div>
          <div class="column-head schedule-head">
            <h2 class="section-title">{{ t("studentHome.weeklyCalendar") }}</h2>
            <span class="pill">{{ t("common.visibleTasks", { count: filteredTaskCount }) }}</span>
          </div>
        </div>

        <div class="calendar-toolbar">
          <button class="btn btn-outline-primary btn-sm" type="button" @click="shiftCalendarWeek(-1)">
            {{ t("common.previousWeek") }}
          </button>
          <button class="btn btn-outline-primary btn-sm" type="button" @click="jumpToCurrentWeek">
            {{ t("common.currentWeek") }}
          </button>
          <button class="btn btn-outline-primary btn-sm" type="button" @click="shiftCalendarWeek(1)">
            {{ t("common.nextWeek") }}
          </button>
        </div>
      </div>

      <div class="schedule-summary">
        <div class="schedule-range">{{ calendarRangeLabel || t("common.pickAWeek") }}</div>
        <div class="search-wrap">
          <input
            v-model="searchQuery"
            class="form-control"
            type="text"
            :placeholder="t('studentHome.searchPlaceholder')"
          />
        </div>
      </div>

      <div v-if="isLoading" class="empty-box schedule-empty mt-3">{{ t("studentHome.loadingSchedule") }}</div>
      <div v-else-if="calendarDays.length === 0" class="empty-box schedule-empty mt-3">{{ t("studentHome.noSchedule") }}</div>
      <div v-else class="schedule-strip">
        <article
          v-for="day in filteredCalendarDays"
          :key="day.date"
          class="schedule-day-card"
          :class="{
            'is-today': isToday(day.date),
            'is-weekend': isWeekend(day.date),
            'has-items': day.items.length > 0,
          }"
        >
          <div class="schedule-day-top">
            <div>
              <div class="schedule-day-name">{{ formatDayName(day.date) }}</div>
              <div class="schedule-day-date">{{ formatMonthDay(day.date) }}</div>
            </div>
            <div class="schedule-day-number">{{ formatDayNumber(day.date) }}</div>
          </div>

          <div class="schedule-day-body">
            <div v-if="day.items.length === 0" class="schedule-empty-card">
              {{ searchQuery.trim() ? t("studentHome.noMatchingTasks") : t("studentHome.noTasksScheduled") }}
            </div>

            <div v-else class="day-task-list">
              <article
                v-for="task in day.items"
                :key="task.task_key"
                class="day-task-item"
                :class="`state-${getTaskState(task, day.date)}`"
              >
                <div class="day-task-main">
                  <div class="day-task-head">
                    <h3 class="day-task-title">{{ task.task_title || task.topic_title }}</h3>
                    <span class="entity-chip" :class="`chip-${getTaskState(task, day.date)}`">
                      {{ getTaskStateLabel(task, day.date) }}
                    </span>
                  </div>
                  <div class="day-task-meta">{{ task.topic_title }} / {{ task.subject_name }}</div>
                </div>

                <div class="day-task-context">
                  <div class="assignment-chip">{{ t("studentHome.groupLabel", { name: task.group_name }) }}</div>
                  <div class="day-task-meta">{{ t("studentHome.teacherLabel", { name: task.teacher_username }) }}</div>
                </div>

                <div class="task-status-copy">{{ getTaskStateCopy(task, day.date) }}</div>

                <button
                  class="btn btn-primary btn-sm action-btn"
                  type="button"
                  :disabled="startingTaskKey === task.task_key || !canStartOrContinueTask(task, day.date)"
                  @click="startTask(task)"
                >
                  {{ startingTaskKey === task.task_key ? t("studentHome.taskButton.opening") : getTaskButtonLabel(task, day.date) }}
                </button>
              </article>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="surface-card section-card">
      <div class="column-head recent-results-head">
        <div>
          <h2 class="section-title">{{ t("studentHome.recentResults") }}</h2>
          <p class="section-subtitle">{{ t("studentHome.recentSubtitle") }}</p>
        </div>
        <span class="pill">{{ t("common.shownCount", { count: recentResultItems.length }) }}</span>
      </div>

      <div v-if="statsLoading" class="empty-box mt-3">{{ t("studentHome.loadingRecentResults") }}</div>
      <div v-else-if="recentResultItems.length === 0" class="empty-box mt-3">
        {{ t("studentHome.noCompletedTests") }}
      </div>
      <div v-else class="recent-results-list">
        <article
          v-for="item in recentResultItems"
          :key="item.attempt_id"
          class="recent-result-item"
        >
          <div class="recent-result-date">
            <div class="recent-result-label">{{ t("common.date") }}</div>
            <div class="recent-result-value">{{ formatResultDate(item.date) }}</div>
          </div>

          <div class="recent-result-main">
            <h3 class="recent-result-title">{{ getRecentResultTitle(item) }}</h3>
            <div class="recent-result-meta">{{ item.topic_title }} / {{ item.subject_name }}</div>
          </div>

          <button
            class="btn btn-outline-primary btn-sm recent-result-action"
            type="button"
            @click="openAttemptResult(item.attempt_id)"
          >
            {{ t("studentHome.viewResults") }}
          </button>
        </article>
      </div>
    </section>

    <section class="surface-card section-card stats-section">
      <h2 class="section-title">{{ t("studentHome.statistics") }}</h2>
      <div v-if="statsLoading" class="empty-box mt-2">{{ t("studentHome.loadingStatistics") }}</div>
      <template v-else>
        <div class="stats-grid">
          <div class="stats-row">
            <span class="stats-label">{{ t("studentHome.completedTasksTrimester") }}</span>
            <span class="stats-value">{{ completedCount }}</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">{{ t("studentHome.passed") }}</span>
            <span class="stats-value">{{ passedCount }}</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">{{ t("studentHome.rating") }}</span>
            <span v-if="rankingLoading" class="stats-value stats-future">{{ t("studentHome.loadingShort") }}</span>
            <span v-else-if="myRank" class="stats-value">
              #{{ myRank.rank }} / {{ myRank.total }}
            </span>
            <span v-else class="stats-value stats-future">-</span>
          </div>
        </div>
      </template>
    </section>

    <section class="surface-card section-card">
      <h2 class="section-title">{{ t("common.notifications") }}</h2>
      <p class="section-subtitle">{{ t("studentHome.notificationsSubtitle") }}</p>

      <div class="push-actions">
        <button class="btn btn-primary btn-sm" type="button" @click="enablePush">
          {{ t("studentHome.enableNotifications") }}
        </button>
        <button
          class="btn btn-outline-primary btn-sm"
          type="button"
          :disabled="testNotifLoading"
          @click="sendTestNotification"
        >
          {{
            testNotifCountdown > 0
              ? t("studentHome.waitSeconds", { seconds: testNotifCountdown })
              : testNotifLoading
                ? t("studentHome.sending")
                : t("studentHome.sendTestNotification")
          }}
        </button>
        <span v-if="testNotifMessage" class="push-test-msg">{{ testNotifMessage }}</span>
        <p v-if="pushSuccess" class="text-success mt-2">{{ pushSuccess }}</p>
        <p v-if="pushError" class="text-danger mt-2">{{ pushError }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped src="./StudentHomePage.css"></style>
