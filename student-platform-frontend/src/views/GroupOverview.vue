<script setup>
import GroupWorkspaceHeader from "@/components/GroupWorkspaceHeader.vue";
import { computed, onActivated, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { apiError } from "@/utils/apiError";
import { Group, Task, Topic } from "@/api.js";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

const props = defineProps(["id"]);
const route = useRoute();
const router = useRouter();
const summaryTab = computed(() => route.query.tab === 'summary');
const resultSearch = computed({
  get: () => typeof route.query.q === 'string' ? route.query.q : '',
  set: (q) => router.replace({ query: { ...route.query, q: q || undefined } }),
});
const resultSort = computed({
  get: () => route.query.sort === 'rank' ? 'rank' : 'name',
  set: (sort) => router.replace({ query: { ...route.query, sort } }),
});
const resultsTab = computed(() => route.query.tab === "results");
const editedDate = ref("");

const WEEK_LENGTH = 7;
const DAY_NAME_FORMAT = { weekday: "short" };
const DAY_NUMBER_FORMAT = { day: "numeric" };
const MONTH_DAY_FORMAT = { month: "short", day: "numeric" };
const MONTH_RANGE_FORMAT = { month: "long", year: "numeric" };
const FULL_DATE_FORMAT = { weekday: "long", month: "long", day: "numeric" };

const { t } = useI18n();
const { formatWithLocale, createCollator } = useLocaleFormatting();

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
const groupLoading = ref(true);
const initializing = ref(true);
const assignmentLoadError = ref('');

const rankingByStudentId = ref({});
const queryDate = () => {
  const value = route.query.date;
  const date = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? parseISODate(value) : null;
  return date && formatISODate(date) === value ? value : formatISODate(new Date());
};
const rankingDate = ref(queryDate());
const rankingLoading = ref(false);
const rankingError = ref("");
let rankingRequest = 0;

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
  groupLoading.value = true;
  loadError.value = "";
  try {
    const response = await Group.get(props.id);
    group.value = {
      ...response,
      students: response.students ?? [],
    };
  } catch {
    loadError.value = t("groupOverview.loadGroupError");
  } finally { groupLoading.value = false; }
};

const loadRanking = async () => {
  const request = ++rankingRequest;
  rankingLoading.value = true;
  rankingError.value = "";
  rankingByStudentId.value = {};
  try {
    const response = await Group.getRanking(props.id, { date: rankingDate.value });
    if (request !== rankingRequest) return;
    const map = {};
    for (const row of response.ranking ?? []) {
      map[row.student_id] = row;
    }
    rankingByStudentId.value = map;
    rankingDate.value = response.results_date || rankingDate.value;
  } catch (error) {
    if (request !== rankingRequest) return;
    if (error?.response?.status === 403) {
      rankingError.value = t("groupOverview.rankingErrors.unlock");
    } else {
      rankingError.value = apiError(error, "groupOverview.rankingErrors.load");
    }
    rankingByStudentId.value = {};
  } finally {
    if (request === rankingRequest) rankingLoading.value = false;
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
  assignmentLoadError.value = '';
  try {
    const assignment = await Group.getTeacherAssignment(props.id);
    savedAssignmentSubject.value = assignment.subject ? String(assignment.subject) : "";
    savedAssignmentSubjectName.value = assignment.subject_name || "";
    savedAssignmentWorkbook.value = assignment.workbook ? String(assignment.workbook) : "";
    savedAssignmentWorkbookName.value = assignment.workbook_title || "";
    await loadTopicsByWorkbook(savedAssignmentWorkbook.value);
  } catch (error) {
    assignmentLoadError.value = apiError(error);
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
    calendarError.value = apiError(error, "groupOverview.calendarErrors.load");
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
    await Promise.all([loadTopicCalendar(), loadRanking()]);
    calendarMessage.value = t("groupOverview.calendarMessages.saved", {
      title: response.task_title || response.topic_title || t("common.task"),
      date: formatWithLocale(parseISODate(day.date), FULL_DATE_FORMAT),
    });
  } catch (error) {
    calendarError.value = apiError(error);
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
    await Promise.all([loadTopicCalendar(), loadRanking()]);
    calendarMessage.value = t("groupOverview.calendarMessages.removed", {
      date: formatWithLocale(parseISODate(day.date), FULL_DATE_FORMAT),
    });
  } catch (error) {
    calendarError.value = apiError(error, "groupOverview.calendarErrors.clear");
  } finally {
    calendarSavingKey.value = "";
  }
};

const shiftRankingDate = async (direction) => {
  const baseDate = selectedRankingDate.value || new Date();
  rankingDate.value = formatISODate(shiftDateByDays(baseDate, direction));
  await onRankingDateChange();
};

const onRankingDateChange = async () => {
  const date = parseISODate(rankingDate.value);
  if (!date || formatISODate(date) !== rankingDate.value) rankingDate.value = formatISODate(new Date());
  await router.push({ query: { ...route.query, date: rankingDate.value } });
};
watch(() => route.query.date, async () => { rankingDate.value = queryDate(); await loadRanking(); });

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
  initializing.value = true;
  await Promise.all([loadGroup(), loadRanking()]);
  await loadTeacherAssignment();
  await loadTopicCalendar();
  if (route.query.task && route.query.topic) {
    const day = calendarDays.value.find(day => isToday(day.date));
    if (day && !day.items.some(item => String(item.task) === String(route.query.task))) {
      await loadTasksByTopic(route.query.topic);
      if (getTasksForTopic(route.query.topic).some(task => String(task.id) === String(route.query.task))) {
        let draft = day.items.find(item => !item.id);
        if (!draft) { draft = createDraftCalendarTask(day.date); day.items.push(draft); }
        draft.topicDraft = String(route.query.topic);
        draft.taskDraft = String(route.query.task);
        editedDate.value = day.date;
      }
    }
  }
  initializing.value = false;
};

const studentCount = computed(() => group.value.students.length);
const visibleStudents = computed(() => {
  const collator = createCollator();
  const query = resultSearch.value.trim().toLocaleLowerCase();
  return group.value.students.filter(student => (student.username || '').toLocaleLowerCase().includes(query))
    .slice().sort((a, b) => {
      if (resultSort.value === 'rank') {
        const difference = (rankingByStudentId.value[a.id]?.rank ?? Infinity) - (rankingByStudentId.value[b.id]?.rank ?? Infinity);
        if (difference && !Number.isNaN(difference)) return difference;
      }
      return collator.compare(a.username || '', b.username || '');
    });
});
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
const hasCalendarDraft = () => calendarDays.value.some(day =>
  day.items.some(item => isCalendarTaskDirty(item) || String(item.topic || '') !== String(item.topicDraft || ''))
  || (day.items.length > 1 && day.items.some(item => !item.id)),
);
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
let activatedOnce = false;
onActivated(async () => {
  if (!activatedOnce) { activatedOnce = true; return; }
  // Refresh server state when returning from membership/settings without discarding edits.
  const hasDraft = hasCalendarDraft();
  await Promise.all([loadGroup(), loadRanking()]);
  await loadTeacherAssignment();
  if (hasDraft) {
    try { await primeCalendarTaskOptions(); }
    catch (error) { calendarError.value = apiError(error); }
  } else {
    await loadTopicCalendar();
  }
});
</script>

<template>
  <div class="group-page">
    <GroupWorkspaceHeader :id="props.id" :name="group.name" :description="group.description"
      :active="summaryTab ? 'summary' : resultsTab ? 'results' : 'schedule'" :subject-id="savedAssignmentSubject" />

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError }} <button class="btn btn-outline-primary" @click="loadGroup">{{ t('ux.retry') }}</button></div>
    <div v-if="assignmentLoadError" class="alert alert-danger" role="alert">{{ assignmentLoadError }} <button class="btn btn-outline-primary" @click="loadOverviewPage">{{ t('ux.retry') }}</button></div>


    <section v-if="summaryTab" class="group-summary" :aria-label="t('workstation.group.summary')">
      <div class="group-metrics">
        <article class="surface-card group-metric"><span>{{ t('common.members') }}</span><strong>{{ groupLoading || loadError ? '—' : studentCount }}</strong></article>
        <article class="surface-card group-metric"><span>{{ t('workstation.group.weekAssignments') }}</span><strong>{{ initializing || calendarLoading || calendarError ? '—' : calendarAssignedCount }}</strong><small>{{ calendarRangeLabel }}</small></article>
        <article class="surface-card group-metric"><span>{{ t('workstation.group.subject') }}</span><strong class="metric-subject">{{ initializing || assignmentLoadError ? '—' : assignmentLabel }}</strong></article>
      </div>
      <div class="surface-card summary-next">
        <h2 class="section-title">{{ t('ux.schedule') }}</h2>
        <p>{{ t('workstation.group.scheduleHint') }}</p>
        <router-link class="btn btn-outline-primary" :to="{ name: 'group-overview', params: { id: props.id } }">{{ t('ux.schedule') }}</router-link>
      </div>
      <div v-if="calendarError" class="alert alert-danger" role="alert">{{ calendarError }}</div>
    </section>

    <section v-if="!resultsTab && !summaryTab" id="group-schedule" class="surface-card schedule-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">{{ t("groupOverview.schedule") }}</h2>
          <span v-if="!calendarLoading && !calendarError" class="pill">{{ t("common.tasksScheduled", { count: calendarAssignedCount }) }}</span>
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

      <div v-if="calendarError" class="alert alert-danger mt-3 mb-0" role="alert">{{ calendarError }}</div>
      <div v-if="calendarMessage" class="alert alert-success mt-3 mb-0" role="status">{{ calendarMessage }}</div>

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
          class="schedule-day-card schedule-editor-day"
          :class="{
            'is-editing': editedDate === day.date,
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

          <div v-if="editedDate !== day.date" class="schedule-summary-list">
            <p v-for="item in day.items" :key="item.clientKey">{{ item.task_title || t('ux.noAssignment') }}</p>
          </div>
          <button class="btn btn-outline-primary btn-sm schedule-edit-toggle" type="button" :aria-expanded="editedDate === day.date" @click="editedDate = editedDate === day.date ? '' : day.date">{{ t(editedDate === day.date ? 'ux.closeEdit' : 'ux.editDay') }}</button>
          <div v-if="editedDate === day.date" class="schedule-task-list">
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
                    :disabled="taskItem.active_question_count < taskItem.questions_per_attempt"
                  >
                    {{ t("ux.taskReady", { title: taskItem.title, active: taskItem.active_question_count, required: taskItem.questions_per_attempt }) }}
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

          <button v-if="editedDate === day.date" class="btn btn-outline-primary btn-sm add-task-btn" type="button" @click="addCalendarTask(day)">
            {{ t("groupOverview.addAnotherTask") }}
          </button>
        </article>
      </div>
    </section>

    <section v-if="resultsTab" class="surface-card members-panel">
      <router-link class="btn btn-outline-primary section-navigation" :to="{ name: 'group-details', params: { id: props.id }, query: { tab: 'results' } }">{{ t("groupDetails.detailedStatistics") }}</router-link>
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
              <label class="field-wrap">{{ t('workstation.group.resultDate') }}
                <input v-model="rankingDate" class="form-control" type="date" :disabled="rankingLoading" @change="onRankingDateChange" />
              </label>
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

        </div>
      </div>

      <p class="helper-copy">{{ t('workstation.group.resultsHint') }}</p>
      <div class="group-result-filters">
        <label class="field-wrap">{{ t('workstation.group.search') }}<input v-model="resultSearch" type="search" class="form-control" /></label>
        <label class="field-wrap">{{ t('workstation.group.sort') }}<select v-model="resultSort" class="form-select"><option value="name">{{ t('workstation.group.name') }}</option><option value="rank">{{ t('workstation.group.rank') }}</option></select></label>
      </div>
      <div v-if="rankingError" class="alert alert-danger compact-alert" role="alert">
        {{ rankingError }}
      </div>

      <div v-if="groupLoading" class="empty-box" role="status">{{ t('ux.loading') }}</div>
      <div v-else-if="!loadError && group.students.length === 0" class="empty-box">{{ t("groupDetails.noStudentsInGroup") }}</div>

      <div v-else-if="!loadError && !visibleStudents.length" class="empty-box">{{ t('ux.noMatches') }} <button class="btn btn-link" @click="resultSearch = ''">{{ t('ux.clearSearch') }}</button></div>
      <div v-else-if="!loadError && !rankingError" class="members-list">
        <article
          v-for="(student, index) in visibleStudents"
          :key="student.id"
          class="member-item"

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
                <router-link
                  v-if="result.attempt_id"
                  :to="{ name: 'attempt-detail', params: { id: result.attempt_id } }"
                  class="entity-chip"
                  :class="result.result === 'success' ? 'chip-success' : 'chip-fail'"
                >
                  {{ result.correct_count }} / {{ result.total_questions }} · {{ t(result.result === 'success' ? 'studentHome.taskState.success' : 'studentHome.taskState.fail') }}
                </router-link>
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

<style scoped src="./GroupDetail.css">@media (max-width: 640px) {
  .schedule-editor-day, .schedule-editor-day.is-editing { grid-template-columns: minmax(0, 1fr); grid-template-areas: "date" "content" "add" "toggle"; }
  .schedule-editor-day .add-task-btn { white-space: normal; justify-self: stretch; }
  .schedule-edit-toggle { justify-self: stretch; }
}
</style>
<style scoped>
.schedule-editor-day {
  grid-template-columns: 150px minmax(0, 1fr) auto;
  grid-template-areas: "date content toggle";
  grid-template-rows: auto;
  align-items: start;
}
.schedule-editor-day.is-editing {
  grid-template-areas: "date content content" ". add toggle";
}
.schedule-editor-day > .schedule-day-top { grid-area: date; }
.schedule-edit-toggle {
  grid-area: toggle;
  align-self: center;
  justify-self: end;
  min-height: 44px;
  position: relative;
  z-index: 1;
}
.schedule-editor-day > .schedule-summary-list,
.schedule-editor-day > .schedule-task-list { grid-area: content; }
.schedule-editor-day > .add-task-btn { grid-area: add; justify-self: start; }
@media (min-width: 701px) and (max-width: 1200px) {
  .schedule-editor-day .schedule-task-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .schedule-editor-day .schedule-topic-state { grid-column: 1; }
  .schedule-editor-day .schedule-day-actions { grid-column: 2; }
}
@media (max-width: 920px) {
  .schedule-editor-day {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas: "date date" "content content" ". toggle";
    grid-template-rows: auto;
  }
  .schedule-editor-day.is-editing {
    grid-template-areas: "date date" "content content" "add toggle";
  }
}
@media (max-width: 640px) {
  .schedule-editor-day, .schedule-editor-day.is-editing { grid-template-columns: minmax(0, 1fr); grid-template-areas: "date" "content" "add" "toggle"; }
  .schedule-editor-day .add-task-btn { white-space: normal; justify-self: stretch; }
  .schedule-edit-toggle { justify-self: stretch; }
}
</style>
