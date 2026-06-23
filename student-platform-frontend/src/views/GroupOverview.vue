<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { Group, Task, Topic } from "@/api.js";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

const props = defineProps(["id"]);

const WEEK_LENGTH = 7;
const DAY_NAME_FORMAT = { weekday: "short" };
const DAY_NUMBER_FORMAT = { day: "numeric" };
const MONTH_DAY_FORMAT = { month: "short", day: "numeric" };
const MONTH_RANGE_FORMAT = { month: "long", year: "numeric" };
const FULL_DATE_FORMAT = { weekday: "long", month: "long", day: "numeric" };
const SHORT_DATE_FORMAT = { day: "2-digit", month: "2-digit", year: "numeric" };

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

let draftTaskCounter = 0;

const createDraftCalendarTask = (date) => ({
  clientKey: `${date}-draft-${draftTaskCounter += 1}`,
  id: null,
  date,
  topic: null,
  topic_title: null,
  task: null,
  task_title: null,
  topicDraft: "",
  taskDraft: "",
});

const normalizeCalendarEntry = (item) => ({
  ...item,
  clientKey: item.id ? `entry-${item.id}` : `empty-${item.date}`,
  topic: item.topic ?? null,
  topic_title: item.topic_title ?? null,
  task: item.task ?? null,
  topicDraft: item.topic ? String(item.topic) : "",
  taskDraft: item.task ? String(item.task) : "",
});

const normalizeCalendarResponse = (response) => {
  const days = [];
  const daysByDate = new Map();

  for (const item of response.results ?? []) {
    if (!daysByDate.has(item.date)) {
      const day = {
        ...item,
        items: [],
      };
      daysByDate.set(item.date, day);
      days.push(day);
    }

    const entry = normalizeCalendarEntry(item);
    if (entry.id || entry.task) {
      daysByDate.get(item.date).items.push(entry);
    }
  }

  return days.map((day) => ({
    ...day,
    items: day.items.length > 0 ? day.items : [createDraftCalendarTask(day.date)],
  }));
};

const group = ref({ students: [], teacher_assignment: null });
const loadError = ref("");

const rankingByStudentId = ref({});
const rankingDate = ref(formatISODate(new Date()));
const rankingDateInput = ref(null);
const rankingLoading = ref(false);
const rankingError = ref("");

const savedAssignmentSubject = ref("");
const savedAssignmentSubjectName = ref("");
const savedAssignmentWorkbook = ref("");
const savedAssignmentWorkbookName = ref("");
const topics = ref([]);
const tasksByTopicId = ref({});

const calendarStartDate = ref(formatISODate(startOfWeek(new Date())));
const calendarDays = ref([]);
const calendarLoading = ref(false);
const calendarError = ref("");
const calendarMessage = ref("");
const calendarSavingKey = ref("");

const loadGroup = async () => {
  loadError.value = "";
  try {
    const response = await Group.get(props.id);
    group.value = {
      ...response,
      students: response.students ?? [],
    };
  } catch {
    loadError.value = t("groupOverview.loadGroupError");
  }
};

const loadRanking = async () => {
  rankingLoading.value = true;
  rankingError.value = "";
  rankingByStudentId.value = {};
  try {
    const response = await Group.getRanking(props.id, { date: rankingDate.value });
    const map = {};
    for (const row of response.ranking ?? []) {
      map[row.student_id] = row;
    }
    rankingByStudentId.value = map;
    rankingDate.value = response.results_date || rankingDate.value;
  } catch (error) {
    if (error?.response?.status === 403) {
      rankingError.value = t("groupOverview.rankingErrors.unlock");
    } else {
      rankingError.value =
        error?.response?.data?.date ||
        error?.response?.data?.detail ||
        t("groupOverview.rankingErrors.load");
    }
    rankingByStudentId.value = {};
  } finally {
    rankingLoading.value = false;
  }
};

const loadTopicsByWorkbook = async (workbookId) => {
  if (!savedAssignmentSubject.value || !workbookId) {
    topics.value = [];
    tasksByTopicId.value = {};
    return;
  }

  const response = await Topic.filter({
    subject: savedAssignmentSubject.value,
    workbook: workbookId,
    is_active: true,
    ordering: "title",
  });
  topics.value = response.results ?? response;
  tasksByTopicId.value = {};
};

const loadTasksByTopic = async (topicId) => {
  if (!topicId) {
    return [];
  }

  const topicKey = String(topicId);
  if (tasksByTopicId.value[topicKey]) {
    return tasksByTopicId.value[topicKey];
  }

  const response = await Task.filter({
    topic: topicKey,
    is_active: true,
    ordering: "title",
  });
  const items = response.results ?? response;
  tasksByTopicId.value = {
    ...tasksByTopicId.value,
    [topicKey]: items,
  };
  return items;
};

const primeCalendarTaskOptions = async () => {
  const topicIds = [
    ...new Set(
      calendarDays.value.flatMap((day) => day.items.map((item) => item.topicDraft).filter(Boolean)),
    ),
  ];
  await Promise.all(topicIds.map((topicId) => loadTasksByTopic(topicId)));
};

const getTasksForTopic = (topicId) => tasksByTopicId.value[String(topicId)] ?? [];

const onTopicChange = async (item) => {
  const tasksForTopic = await loadTasksByTopic(item.topicDraft);
  if (!tasksForTopic.some((taskItem) => String(taskItem.id) === String(item.taskDraft || ""))) {
    item.taskDraft = "";
  }
};

const loadTeacherAssignment = async () => {
  try {
    const assignment = await Group.getTeacherAssignment(props.id);
    savedAssignmentSubject.value = assignment.subject ? String(assignment.subject) : "";
    savedAssignmentSubjectName.value = assignment.subject_name || "";
    savedAssignmentWorkbook.value = assignment.workbook ? String(assignment.workbook) : "";
    savedAssignmentWorkbookName.value = assignment.workbook_title || "";
    await loadTopicsByWorkbook(savedAssignmentWorkbook.value);
  } catch {
    savedAssignmentSubject.value = "";
    savedAssignmentSubjectName.value = "";
    savedAssignmentWorkbook.value = "";
    savedAssignmentWorkbookName.value = "";
    topics.value = [];
    tasksByTopicId.value = {};
  }
};

const loadTopicCalendar = async () => {
  calendarError.value = "";
  calendarLoading.value = true;
  try {
    const response = await Group.getTopicCalendar(props.id, {
      start_date: calendarStartDate.value,
      days: WEEK_LENGTH,
    });
    calendarDays.value = normalizeCalendarResponse(response);
    await primeCalendarTaskOptions();
  } catch (error) {
    calendarError.value =
      error?.response?.data?.detail || t("groupOverview.calendarErrors.load");
    calendarDays.value = [];
  } finally {
    calendarLoading.value = false;
  }
};

const shiftCalendarWeek = async (direction) => {
  const nextStartDate = shiftDateByDays(
    parseISODate(calendarStartDate.value),
    direction * WEEK_LENGTH,
  );
  calendarStartDate.value = formatISODate(nextStartDate);
  await loadTopicCalendar();
};

const jumpToCurrentWeek = async () => {
  calendarStartDate.value = formatISODate(startOfWeek(new Date()));
  await loadTopicCalendar();
};

const addCalendarTask = (day) => {
  day.items.push(createDraftCalendarTask(day.date));
};

const removeCalendarDraft = (day, item) => {
  day.items = day.items.filter((entry) => entry.clientKey !== item.clientKey);
  if (day.items.length === 0) {
    day.items.push(createDraftCalendarTask(day.date));
  }
};

const saveCalendarTask = async (day, item) => {
  if (!item.taskDraft) {
    return;
  }

  calendarError.value = "";
  calendarMessage.value = "";
  calendarSavingKey.value = item.clientKey;
  try {
    const response = await Group.saveTopicCalendarItem(props.id, {
      date: day.date,
      task: Number(item.taskDraft),
    });
    await loadTopicCalendar();
    calendarMessage.value = t("groupOverview.calendarMessages.saved", {
      title: response.task_title || response.topic_title || t("common.task"),
      date: formatWithLocale(parseISODate(day.date), FULL_DATE_FORMAT),
    });
  } catch (error) {
    calendarError.value =
      error?.response?.data?.task?.[0] ||
      error?.response?.data?.detail ||
      t("groupOverview.calendarErrors.save");
  } finally {
    calendarSavingKey.value = "";
  }
};

const clearCalendarTask = async (day, item) => {
  if (!item.id) {
    removeCalendarDraft(day, item);
    return;
  }

  calendarError.value = "";
  calendarMessage.value = "";
  calendarSavingKey.value = item.clientKey;
  try {
    await Group.clearTopicCalendarItem(props.id, { schedule_entry: item.id });
    await loadTopicCalendar();
    calendarMessage.value = t("groupOverview.calendarMessages.removed", {
      date: formatWithLocale(parseISODate(day.date), FULL_DATE_FORMAT),
    });
  } catch (error) {
    calendarError.value =
      error?.response?.data?.detail || t("groupOverview.calendarErrors.clear");
  } finally {
    calendarSavingKey.value = "";
  }
};

const shiftRankingDate = async (direction) => {
  const baseDate = selectedRankingDate.value || new Date();
  rankingDate.value = formatISODate(shiftDateByDays(baseDate, direction));
  await loadRanking();
};

const openRankingDatePicker = () => {
  const input = rankingDateInput.value;
  if (!input || rankingLoading.value) {
    return;
  }
  if (typeof input.showPicker === "function") {
    input.showPicker();
    return;
  }
  input.focus();
  input.click();
};

const onRankingDateChange = async () => {
  if (!selectedRankingDate.value) {
    rankingDate.value = formatISODate(new Date());
  }
  await loadRanking();
};

const resetPageState = () => {
  group.value = { students: [], teacher_assignment: null };
  loadError.value = "";
  rankingByStudentId.value = {};
  rankingDate.value = formatISODate(new Date());
  rankingError.value = "";
  savedAssignmentSubject.value = "";
  savedAssignmentSubjectName.value = "";
  savedAssignmentWorkbook.value = "";
  savedAssignmentWorkbookName.value = "";
  topics.value = [];
  tasksByTopicId.value = {};
  calendarStartDate.value = formatISODate(startOfWeek(new Date()));
  calendarDays.value = [];
  calendarError.value = "";
  calendarMessage.value = "";
  calendarSavingKey.value = "";
};

const loadOverviewPage = async () => {
  await Promise.all([loadGroup(), loadRanking()]);
  await loadTeacherAssignment();
  await loadTopicCalendar();
};

const studentCount = computed(() => group.value.students.length);
const assignmentLabel = computed(() => {
  if (!savedAssignmentSubjectName.value) {
    return t("groupOverview.assignmentMessages.notAssigned");
  }
  if (!savedAssignmentWorkbookName.value) {
    return savedAssignmentSubjectName.value;
  }
  return `${savedAssignmentSubjectName.value} / ${savedAssignmentWorkbookName.value}`;
});
const scheduleDisabledMessage = computed(() => {
  if (!savedAssignmentSubject.value) {
    return t("groupOverview.assignmentMessages.missingSubject");
  }
  if (!savedAssignmentWorkbook.value) {
    return t("groupOverview.assignmentMessages.missingTextbook");
  }
  return "";
});
const calendarAssignedCount = computed(
  () => calendarDays.value.reduce(
    (sum, day) => sum + day.items.filter((item) => Boolean(item.task)).length,
    0,
  ),
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
  return `${formatWithLocale(first, MONTH_RANGE_FORMAT)} | ${formatWithLocale(first, MONTH_DAY_FORMAT)} - ${formatWithLocale(last, MONTH_DAY_FORMAT)}`;
});
const selectedRankingDate = computed(() => parseISODate(rankingDate.value));
const isViewingToday = computed(() => isToday(rankingDate.value));
const rankingDateButtonLabel = computed(() => {
  if (!selectedRankingDate.value) {
    return t("groupOverview.selectDate");
  }
  return formatWithLocale(selectedRankingDate.value, SHORT_DATE_FORMAT);
});
const memberEmptyResultsLabel = computed(() => {
  if (!selectedRankingDate.value) {
    return t("groupOverview.noTestsOnDate");
  }
  if (isViewingToday.value) {
    return t("groupOverview.noTestsToday");
  }
  return t("groupOverview.noTestsOnFormattedDate", {
    date: formatWithLocale(selectedRankingDate.value, MONTH_DAY_FORMAT),
  });
});

const isCalendarTaskDirty = (item) =>
  (item.task ? String(item.task) : "") !== String(item.taskDraft || "");
const isToday = (value) => formatISODate(new Date()) === value;
const isWeekend = (value) => {
  const date = parseISODate(value);
  const day = date?.getDay();
  return day === 0 || day === 6;
};
const formatDayName = (value) => formatWithLocale(parseISODate(value), DAY_NAME_FORMAT);
const formatDayNumber = (value) => formatWithLocale(parseISODate(value), DAY_NUMBER_FORMAT);
const formatMonthDay = (value) => formatWithLocale(parseISODate(value), MONTH_DAY_FORMAT);
const getStudentResults = (studentId) => rankingByStudentId.value[studentId]?.today_results ?? [];
const formatMemberRank = (rank) =>
  rank == null ? t("groupOverview.formatRankEmpty") : t("groupOverview.formatRank", { rank });

watch(
  () => props.id,
  async () => {
    resetPageState();
    await loadOverviewPage();
  },
);

onMounted(async () => {
  await loadOverviewPage();
});
</script>

<template>
  <div class="group-page">
    <section class="surface-card group-hero">
      <div class="hero-topline">
        <div class="hero-heading-row">
          <span class="pill">{{ t("groupOverview.badge") }}</span>
          <h1 class="group-title">{{ group.name || t("common.untitledGroup") }}</h1>
        </div>
      </div>

      <div class="hero-copy">
        <p class="group-description">{{ group.description || t("common.noDescriptionAvailable") }}</p>
      </div>

      <div class="hero-summary-row">
        <div class="hero-meta">
          <div class="meta-card">
            <div class="meta-label">{{ t("common.members") }}</div>
            <div class="meta-value">{{ studentCount }}</div>
          </div>
          <div class="meta-card meta-card-wide">
            <div class="meta-label">{{ t("common.subject") }}</div>
            <div class="meta-value meta-value-small">{{ assignmentLabel }}</div>
          </div>
        </div>

        <router-link
          class="hero-link-button hero-link-primary"
          :to="{ name: 'group-details', params: { id: props.id } }"
        >
          {{ t("groupDetails.badge") }}
        </router-link>
        <router-link class="home-link hero-link-button hero-link-secondary" to="/">
          {{ t("common.backToDashboard") }}
        </router-link>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section class="surface-card schedule-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">{{ t("groupOverview.schedule") }}</h2>
          <span class="pill">{{ t("common.tasksScheduled", { count: calendarAssignedCount }) }}</span>
        </div>
      </div>

      <div class="schedule-header">
        <p class="assignment-hint schedule-hint">
          {{ t("groupOverview.assignmentHint") }}
        </p>

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
        <div class="schedule-subject">
          {{ t("groupOverview.taskPool") }}
          <strong>{{ assignmentLabel }}</strong>
        </div>
      </div>

      <div v-if="calendarError" class="alert alert-danger mt-3 mb-0">{{ calendarError }}</div>
      <div v-if="calendarMessage" class="alert alert-success mt-3 mb-0">{{ calendarMessage }}</div>

      <div v-if="calendarLoading" class="empty-box schedule-empty mt-3">
        {{ t("groupOverview.loadingSchedule") }}
      </div>

      <div v-else-if="scheduleDisabledMessage" class="schedule-empty">
        <div class="schedule-empty-title">{{ t("groupOverview.waitingForSetup") }}</div>
        <p class="schedule-empty-copy">
          {{ scheduleDisabledMessage }}
          <router-link class="inline-link" :to="{ name: 'group-details', params: { id: props.id } }">
            {{ t("groupOverview.openGroupDetails") }}
          </router-link>
        </p>
      </div>

      <div v-else-if="topics.length === 0" class="schedule-empty">
        <div class="schedule-empty-title">{{ t("groupOverview.noActiveLessons") }}</div>
        <p class="schedule-empty-copy">
          {{ t("groupOverview.noActiveLessonsCopy") }}
        </p>
      </div>

      <div v-else class="schedule-strip">
        <article
          v-for="day in calendarDays"
          :key="day.date"
          class="schedule-day-card"
          :class="{
            'is-today': isToday(day.date),
            'is-weekend': isWeekend(day.date),
            'is-assigned': day.items.some((item) => item.task),
          }"
        >
          <div class="schedule-day-top">
            <div>
              <div class="schedule-day-name">{{ formatDayName(day.date) }}</div>
              <div class="schedule-day-date">{{ formatMonthDay(day.date) }}</div>
            </div>
            <div class="schedule-day-number">{{ formatDayNumber(day.date) }}</div>
          </div>

          <div class="schedule-task-list">
            <article
              v-for="item in day.items"
              :key="item.clientKey"
              class="schedule-task-row"
            >
              <div class="schedule-field">
                <label class="form-label schedule-label">{{ t("common.lesson") }}</label>
                <select
                  v-model="item.topicDraft"
                  class="form-select form-select-sm schedule-select"
                  :disabled="topics.length === 0"
                  :aria-label="t('common.lesson')"
                  @change="onTopicChange(item)"
                >
                  <option value="">
                    {{ topics.length ? t("groupOverview.chooseLesson") : t("groupOverview.noLessonsInTextbook") }}
                  </option>
                  <option v-for="topicItem in topics" :key="topicItem.id" :value="String(topicItem.id)">
                    {{ topicItem.title }}
                  </option>
                </select>
              </div>

              <div class="schedule-field">
                <label class="form-label schedule-label">{{ t("common.task") }}</label>
                <select
                  v-model="item.taskDraft"
                  class="form-select form-select-sm schedule-select"
                  :disabled="!item.topicDraft"
                  :aria-label="t('common.task')"
                >
                  <option value="">
                    {{ item.topicDraft ? t("groupOverview.chooseTask") : t("groupOverview.chooseLessonFirst") }}
                  </option>
                  <option
                    v-for="taskItem in getTasksForTopic(item.topicDraft)"
                    :key="taskItem.id"
                    :value="String(taskItem.id)"
                  >
                    {{ taskItem.title }}
                  </option>
                </select>
              </div>

              <div class="schedule-topic-state">
                <span class="schedule-topic-caption">{{ t("common.current") }}</span>
                <strong>{{ item.task_title || item.topic_title || t("common.freeSlot") }}</strong>
              </div>

              <div class="schedule-day-actions">
                <button
                  class="btn btn-primary btn-sm"
                  type="button"
                  :disabled="calendarSavingKey === item.clientKey || !item.taskDraft || !isCalendarTaskDirty(item)"
                  @click="saveCalendarTask(day, item)"
                >
                  {{ calendarSavingKey === item.clientKey ? t("common.saving") : t("groupOverview.saveShort") }}
                </button>
                <button
                  class="btn btn-outline-secondary btn-sm"
                  type="button"
                  :disabled="calendarSavingKey === item.clientKey || (!item.id && day.items.length === 1 && !item.taskDraft)"
                  @click="clearCalendarTask(day, item)"
                >
                  {{ t("groupOverview.clearShort") }}
                </button>
              </div>
            </article>
          </div>

          <button class="btn btn-outline-primary btn-sm add-task-btn" type="button" @click="addCalendarTask(day)">
            {{ t("groupOverview.addAnotherTask") }}
          </button>
        </article>
      </div>
    </section>

    <section class="surface-card members-panel">
      <div class="panel-header">
        <div class="members-title-row">
          <h2 class="section-title">{{ t("groupOverview.results") }}</h2>
          <span class="pill">{{ t("common.studentsCount", { count: studentCount }) }}</span>
        </div>
      </div>

      <div class="members-toolbar">
        <div class="member-results-toolbar">
          <div class="member-results-controls">
            <div class="member-nav-group">
              <button
                class="btn btn-outline-primary btn-sm member-nav-btn"
                type="button"
                :disabled="rankingLoading"
                :aria-label="t('groupOverview.previousDate')"
                @click="shiftRankingDate(-1)"
              >
                <span aria-hidden="true">&lt;</span>
              </button>
              <button
                class="member-current-date-btn"
                type="button"
                :disabled="rankingLoading"
                aria-live="polite"
                @click="openRankingDatePicker"
              >
                {{ rankingDateButtonLabel }}
              </button>
              <button
                class="btn btn-outline-primary btn-sm member-nav-btn"
                type="button"
                :disabled="rankingLoading"
                :aria-label="t('groupOverview.nextDate')"
                @click="shiftRankingDate(1)"
              >
                <span aria-hidden="true">&gt;</span>
              </button>
            </div>
          </div>
          <input
            id="member-results-date"
            ref="rankingDateInput"
            v-model="rankingDate"
            class="member-date-input-hidden"
            type="date"
            :disabled="rankingLoading"
            @change="onRankingDateChange"
          />
        </div>
      </div>

      <div v-if="rankingError" class="alert alert-danger compact-alert">
        {{ rankingError }}
      </div>

      <div v-if="group.students.length === 0" class="empty-box">{{ t("groupDetails.noStudentsInGroup") }}</div>

      <div v-else class="members-list">
        <article
          v-for="(student, index) in group.students"
          :key="student.id"
          class="member-item"
          :style="{ '--delay': `${index * 38}ms` }"
        >
          <div class="member-index">#{{ index + 1 }}</div>
          <div class="member-info">
            <div class="member-name">{{ student.username || t("common.unknown") }}</div>
            <div class="member-meta member-rank-row">
              <span>{{ formatMemberRank(rankingByStudentId[student.id]?.rank) }}</span>
              <span
                v-if="rankingByStudentId[student.id]?.rank_trend === 'up'"
                class="member-rank-trend trend-up"
                :title="t('groupDetails.rankImproved')"
              >
                &uarr;
              </span>
              <span
                v-else-if="rankingByStudentId[student.id]?.rank_trend === 'down'"
                class="member-rank-trend trend-down"
                :title="t('groupDetails.rankDropped')"
              >
                &darr;
              </span>
            </div>
          </div>
          <div class="member-last-result">
            <div v-if="rankingLoading" class="member-result-placeholder">{{ t("common.loading") }}</div>
            <div
              v-else-if="getStudentResults(student.id).length"
              class="member-results-list"
            >
              <div
                v-for="result in getStudentResults(student.id)"
                :key="result.schedule_entry_id"
                class="member-result-item"
              >
                <span class="member-result-task">
                  {{ result.task_title || result.topic_title || t("common.task") }}
                </span>
                <span
                  v-if="result.result"
                  class="entity-chip"
                  :class="result.result === 'success' ? 'chip-success' : 'chip-fail'"
                >
                  {{ result.correct_count }} / {{ result.total_questions }}
                </span>
                <span v-else class="member-result-placeholder">{{ t("common.noResultYet") }}</span>
              </div>
            </div>
            <span v-else class="member-result-placeholder">{{ memberEmptyResultsLabel }}</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped src="./GroupDetail.css"></style>
