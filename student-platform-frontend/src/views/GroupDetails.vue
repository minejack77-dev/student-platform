<script setup>
import GroupWorkspaceHeader from "@/components/GroupWorkspaceHeader.vue";
import { apiError } from "@/utils/apiError";
import axios from "axios";
import { useRoute } from "vue-router";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { Group, Subject, Workbook } from "@/api.js";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

const props = defineProps(["id"]);
const route = useRoute();
const resultsTab = computed(() => route.query.tab === "results");
const confirmRemove = ref(false);
const pendingRemoval = ref(null);
const membersTab = computed(() => route.query.tab === 'members');

const MONTH_DAY_FORMAT = { month: "short", day: "numeric" };
const WEEKDAY_FORMAT = { weekday: "short" };
const LONG_DATE_FORMAT = { month: "long", day: "numeric", year: "numeric" };

const { t } = useI18n();
const { createCollator, formatWithLocale } = useLocaleFormatting();

const parseISODate = (value) => {
  const [year, month, day] = (value || "").split("-").map(Number);
  if (!year || !month || !day) {
    return null;
  }
  return new Date(year, month - 1, day);
};

const createEmptyStatistics = () => ({
  scale: "week",
  start_date: "",
  end_date: "",
  dates: [],
  students: [],
});

const group = ref({ students: [], teacher_assignment: null });
const loadError = ref("");

const subjects = ref([]);
const workbooks = ref([]);
const assignmentForm = ref({
  subject: "",
  workbook: "",
});
const savedAssignmentSubject = ref("");
const savedAssignmentWorkbook = ref("");
const assignmentLoading = ref(false);
const assignmentError = ref("");
const assignmentSuccess = ref("");

const statistics = ref(createEmptyStatistics());
const statisticsTable = ref(null);
watch([statistics, resultsTab], async () => {
  await nextTick();
  if (statisticsTable.value) statisticsTable.value.scrollLeft = statisticsTable.value.scrollWidth;
}, {flush: 'post'});
const statisticsScale = ref("week");
const statisticsEndDate = ref(new Date().toLocaleDateString("en-CA"));
const statisticsSortMode = ref("name");
const statisticsLoading = ref(false);
const statisticsError = ref("");

const searchQuery = ref("");
const searchResults = ref([]);
const searchError = ref("");
const searchLoading = ref(false);
const addLoadingUserId = ref(null);
const removeLoadingUserId = ref(null);
const addResultMessage = ref("");
let searchDebounceTimer = null;

const statScales = computed(() => [
  { value: "week", label: t("groupDetails.scales.week") },
  { value: "month", label: t("groupDetails.scales.month") },
  { value: "three_months", label: t("groupDetails.scales.threeMonths") },
]);

const statLegend = computed(() => [
  { state: "all_correct", label: t("groupDetails.legend.allCorrect") },
  { state: "partial", label: t("groupDetails.legend.partial") },
  { state: "none_correct", label: t("groupDetails.legend.noneCorrect") },
  { state: "missed", label: t("groupDetails.legend.missed") },
  { state: "pending", label: t("ux.status.pending") },
  { state: "no_test", label: t("groupDetails.legend.noTest") },
]);

const loadGroup = async () => {
  loadError.value = "";
  try {
    const response = await Group.get(props.id);
    group.value = {
      ...response,
      students: response.students ?? [],
    };
  } catch {
    loadError.value = t("groupDetails.loadError");
  }
};

const loadSubjects = async () => {
  const response = await Subject.filter({ is_active: true, ordering: "name" });
  subjects.value = response.results ?? response;
};

const loadWorkbooks = async (subjectId) => {
  if (!subjectId) {
    workbooks.value = [];
    return;
  }
  const response = await Workbook.filter({
    subject: subjectId,
    is_active: true,
    ordering: "title",
  });
  workbooks.value = response.results ?? response;
};

const loadTeacherAssignment = async () => {
  assignmentError.value = "";
  try {
    const assignment = await Group.getTeacherAssignment(props.id);
    assignmentForm.value.subject = assignment.subject ? String(assignment.subject) : "";
    await loadWorkbooks(assignmentForm.value.subject);
    assignmentForm.value.workbook = assignment.workbook ? String(assignment.workbook) : "";
    savedAssignmentSubject.value = assignmentForm.value.subject;
    savedAssignmentWorkbook.value = assignmentForm.value.workbook;
  } catch (error) {
    assignmentError.value = apiError(error, "groupDetails.assignmentLoadError");
    assignmentForm.value = { subject: "", workbook: "" };
    savedAssignmentSubject.value = "";
    savedAssignmentWorkbook.value = "";
    workbooks.value = [];
  }
};

const loadDetailedStatistics = async () => {
  statisticsLoading.value = true;
  statisticsError.value = "";
  try {
    statistics.value = await Group.getDetailedStatistics(props.id, {
      scale: statisticsScale.value,
      end_date: statisticsEndDate.value,
    });
  } catch (error) {
    statisticsError.value = apiError(error, "groupDetails.statisticsLoadError");
    statistics.value = createEmptyStatistics();
  } finally {
    statisticsLoading.value = false;
  }
};

const saveTeacherAssignment = async () => {
  if (!assignmentForm.value.subject && savedAssignmentSubject.value) { confirmRemove.value = true; return; }
  assignmentError.value = "";
  assignmentSuccess.value = "";
  assignmentLoading.value = true;
  try {
    const subjectId = assignmentForm.value.subject
      ? Number(assignmentForm.value.subject)
      : null;
    const workbookId = assignmentForm.value.workbook
      ? Number(assignmentForm.value.workbook)
      : null;
    if (!subjectId) {
      await Group.clearTeacherAssignment(props.id);
      assignmentForm.value = { subject: "", workbook: "" };
      savedAssignmentSubject.value = "";
      savedAssignmentWorkbook.value = "";
      workbooks.value = [];
      assignmentSuccess.value = t("groupDetails.assignmentMessages.removed");
    } else {
      const response = await Group.saveTeacherAssignment(props.id, {
        subject: subjectId,
        workbook: workbookId,
        topic: null,
        task: null,
      });
      assignmentForm.value.subject = response.subject ? String(response.subject) : "";
      await loadWorkbooks(assignmentForm.value.subject);
      assignmentForm.value.workbook = response.workbook ? String(response.workbook) : "";
      savedAssignmentSubject.value = assignmentForm.value.subject;
      savedAssignmentWorkbook.value = assignmentForm.value.workbook;
      assignmentSuccess.value = t("groupDetails.assignmentMessages.saved");
    }
    await loadGroup();
  } catch (error) {
    assignmentError.value = apiError(error, "groupDetails.assignmentMessages.saveError");
  } finally {
    assignmentLoading.value = false;
  }
};

const clearTeacherAssignment = async () => {
  confirmRemove.value = false;
  assignmentError.value = "";
  assignmentSuccess.value = "";
  assignmentLoading.value = true;
  try {
    await Group.clearTeacherAssignment(props.id);
    assignmentForm.value = { subject: "", workbook: "" };
    savedAssignmentSubject.value = "";
    savedAssignmentWorkbook.value = "";
    workbooks.value = [];
    assignmentSuccess.value = t("groupDetails.assignmentMessages.removed");
    await loadGroup();
  } catch (error) {
    assignmentError.value = apiError(error, "groupDetails.assignmentMessages.removeError");
  } finally {
    assignmentLoading.value = false;
  }
};

const onSubjectChange = async () => {
  assignmentForm.value.workbook = "";
  assignmentSuccess.value = "";
  assignmentError.value = '';
  try {
    await loadWorkbooks(assignmentForm.value.subject);
  } catch (error) {
    workbooks.value = [];
    assignmentError.value = apiError(error, 'groupDetails.assignmentLoadError');
  }
};

const searchStudents = async (query) => {
  if (!query) {
    searchResults.value = [];
    return;
  }

  searchLoading.value = true;
  searchError.value = "";
  try {
    const response = await axios.get(`/api/group/${props.id}/search-students/`, {
      params: { q: query },
    });
    searchResults.value = response.data ?? [];
  } catch (error) {
    searchResults.value = [];
    searchError.value = apiError(error, "groupDetails.searchError");
  } finally {
    searchLoading.value = false;
  }
};

const addStudentToGroup = async (student) => {
  addResultMessage.value = "";
  addLoadingUserId.value = student.user;

  try {
    const response = await axios.post(`/api/group/${props.id}/add-student/`, {
      user_id: student.user,
    });

    addResultMessage.value = response.data?.added
      ? t("groupDetails.studentMessages.added")
      : t("groupDetails.studentMessages.alreadyInGroup");

    searchResults.value = searchResults.value.map((item) =>
      item.user === student.user ? { ...item, in_group: true } : item,
    );
    await Promise.all([loadGroup(), loadDetailedStatistics()]);
  } catch (error) {
    addResultMessage.value = apiError(error, "groupDetails.studentMessages.addError");
  } finally {
    addLoadingUserId.value = null;
  }
};

const removeStudentFromGroup = async (student) => {
  pendingRemoval.value = null;
  addResultMessage.value = "";
  removeLoadingUserId.value = student.user;
  try {
    const response = await axios.post(`/api/group/${props.id}/remove-student/`, {
      user_id: student.user,
    });

    if (response.data?.removed) {
      addResultMessage.value = t("groupDetails.studentMessages.removed");
      group.value.students = group.value.students.filter((item) => item.id !== student.id);
      searchResults.value = searchResults.value.map((item) =>
        item.user === student.user ? { ...item, in_group: false } : item,
      );
      await loadDetailedStatistics();
    } else {
      addResultMessage.value = t("groupDetails.studentMessages.notInGroup");
    }
  } catch (error) {
    addResultMessage.value = apiError(error, "groupDetails.studentMessages.removeError");
  } finally {
    removeLoadingUserId.value = null;
  }
};

const setStatisticsScale = async (scale) => {
  if (statisticsScale.value === scale || statisticsLoading.value) {
    return;
  }
  statisticsScale.value = scale;
  await loadDetailedStatistics();
};

const resetPageState = () => {
  group.value = { students: [], teacher_assignment: null };
  loadError.value = "";
  subjects.value = [];
  workbooks.value = [];
  assignmentForm.value = { subject: "", workbook: "" };
  savedAssignmentSubject.value = "";
  savedAssignmentWorkbook.value = "";
  assignmentLoading.value = false;
  assignmentError.value = "";
  assignmentSuccess.value = "";
  statistics.value = createEmptyStatistics();
  statisticsScale.value = "week";
  statisticsSortMode.value = "name";
  statisticsLoading.value = false;
  statisticsError.value = "";
  searchQuery.value = "";
  searchResults.value = [];
  searchError.value = "";
  searchLoading.value = false;
  addLoadingUserId.value = null;
  removeLoadingUserId.value = null;
  addResultMessage.value = "";
};

const loadDetailsPage = async () => {
  loadError.value = "";
  try {
    await Promise.all([loadGroup(), loadSubjects(), loadDetailedStatistics()]);
    await loadTeacherAssignment();
  } catch {
    loadError.value = t("groupDetails.pageLoadError");
  }
};

const studentCount = computed(() => group.value.students.length);
const currentSubjectLabel = computed(() => {
  const subjectName = group.value.teacher_assignment?.subject_name;
  const workbookTitle = group.value.teacher_assignment?.workbook_title;
  if (!subjectName) {
    return t("common.notAssignedYet");
  }
  if (!workbookTitle) {
    return subjectName;
  }
  return `${subjectName} / ${workbookTitle}`;
});
const statisticsRangeLabel = computed(() => {
  const startDate = parseISODate(statistics.value.start_date);
  const endDate = parseISODate(statistics.value.end_date);
  if (!startDate || !endDate) {
    return "";
  }
  return `${formatWithLocale(startDate, LONG_DATE_FORMAT)} - ${formatWithLocale(endDate, LONG_DATE_FORMAT)}`;
});
const hasScheduledTests = computed(() =>
  (statistics.value.dates ?? []).some((column) => column.scheduled_count > 0),
);
const statisticsSortLabel = computed(() =>
  statisticsSortMode.value === "rank"
    ? t("groupDetails.sortModes.rank")
    : t("groupDetails.sortModes.name"),
);
const sortedStatisticsStudents = computed(() => {
  const rows = [...(statistics.value.students ?? [])];
  const studentNameCollator = createCollator({
    numeric: true,
    sensitivity: "base",
  });

  if (statisticsSortMode.value === "rank") {
    rows.sort((left, right) => {
      const leftRank = left.rank ?? Number.POSITIVE_INFINITY;
      const rightRank = right.rank ?? Number.POSITIVE_INFINITY;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return studentNameCollator.compare(left.username ?? "", right.username ?? "");
    });
    return rows;
  }

  rows.sort((left, right) =>
    studentNameCollator.compare(left.username ?? "", right.username ?? ""),
  );
  return rows;
});

const formatStatisticsDay = (value) => {
  const date = parseISODate(value);
  return date ? formatWithLocale(date, MONTH_DAY_FORMAT) : value;
};

const formatStatisticsWeekday = (value) => {
  const date = parseISODate(value);
  return date ? formatWithLocale(date, WEEKDAY_FORMAT) : "";
};

const formatTestOutcome = (test) => {
  if (["not_ready", "not_started", "in_progress", "upcoming"].includes(test.result)) return t(`ux.status.${test.result}`);
  if (test.result === "missed") {
    return t("groupDetails.missed");
  }
  if (test.correct_count == null || test.total_questions == null) {
    return t("groupDetails.noResult");
  }
  return `${test.correct_count} / ${test.total_questions}`;
};

const statisticsRankLabel = (rank) =>
  rank == null ? t("groupDetails.rankDash") : t("groupDetails.rankLabel", { rank });

const toggleStatisticsSort = () => {
  statisticsSortMode.value = statisticsSortMode.value === "name" ? "rank" : "name";
};

watch(
  () => props.id,
  async () => {
    resetPageState();
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
    await loadDetailsPage();
  },
);

watch(searchQuery, (value) => {
  addResultMessage.value = "";
  searchError.value = "";

  const trimmed = value.trim();
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }

  if (!trimmed) {
    searchResults.value = [];
    searchLoading.value = false;
    return;
  }

  searchDebounceTimer = setTimeout(() => {
    searchStudents(trimmed);
  }, 250);
});

onMounted(async () => {
  await loadDetailsPage();
});
let activatedOnce = false;
onActivated(async () => {
  if (!activatedOnce) { activatedOnce = true; return; }
  const dirty = assignmentForm.value.subject !== savedAssignmentSubject.value || assignmentForm.value.workbook !== savedAssignmentWorkbook.value;
  await Promise.all([loadGroup(), loadDetailedStatistics()]);
  if (!dirty) await loadTeacherAssignment();
});

onBeforeUnmount(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
});
</script>

<template>
  <div class="group-page">
    <GroupWorkspaceHeader :id="props.id" :name="group.name" :description="group.description"
      :active="resultsTab ? 'results' : membersTab ? 'members' : 'settings'" :subject-id="savedAssignmentSubject" />

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError }} <button class="btn btn-outline-primary" @click="loadDetailsPage">{{ t('ux.retry') }}</button></div>

    <ConfirmDialog v-if="pendingRemoval" :title="t('workstation.group.removeTitle')" :description="t('workstation.group.removeDescription', { name: pendingRemoval.username })" :confirm-label="t('common.remove')" @confirm="removeStudentFromGroup(pendingRemoval)" @cancel="pendingRemoval = null" />
    <ConfirmDialog v-if="confirmRemove" :title="t('ux.removeSubject')" :description="t('ux.removeSubjectConfirm')" :confirm-label="t('ux.removeSubject')" @confirm="clearTeacherAssignment" @cancel="confirmRemove = false" />

    <section v-if="!resultsTab && !membersTab" class="surface-card assignment-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">{{ t("common.subject") }}</h2>
          <span class="pill">{{ t("groupDetails.subjectBadge") }}</span>
        </div>
      </div>

      <p class="assignment-hint">
        {{ t("groupDetails.assignmentHint") }}
      </p>

      <div class="row g-3">
        <div class="col-md-6">
          <label for="group-subject" class="form-label">{{ t("common.subject") }}</label>
          <select id="group-subject" v-model="assignmentForm.subject" class="form-select" @change="onSubjectChange">
            <option value="">{{ t("groupDetails.noSubjectSelected") }}</option>
            <option v-for="subject in subjects" :key="subject.id" :value="String(subject.id)">
              {{ subject.name }}
            </option>
          </select>
        </div>
        <div class="col-md-6">
          <label for="group-workbook" class="form-label">{{ t("common.textbook") }}</label>
          <select id="group-workbook" v-model="assignmentForm.workbook" class="form-select" :disabled="!assignmentForm.subject">
            <option value="">
              {{
                assignmentForm.subject
                  ? t("groupDetails.noTextbookSelected")
                  : t("groupDetails.chooseSubjectFirst")
              }}
            </option>
            <option v-for="workbook in workbooks" :key="workbook.id" :value="String(workbook.id)">
              {{ workbook.title }}
            </option>
          </select>
        </div>
      </div>

      <div class="assignment-actions">
        <button class="btn btn-outline-secondary" :disabled="assignmentLoading" @click="assignmentForm = {subject: savedAssignmentSubject, workbook: savedAssignmentWorkbook}; loadWorkbooks(savedAssignmentSubject)">{{ t('ux.resetForm') }}</button>
        <button class="btn btn-primary" type="button" :disabled="assignmentLoading" @click="saveTeacherAssignment">
          {{ assignmentLoading ? t("common.saving") : t("groupDetails.saveAssignment") }}
        </button>
        <button
          class="btn btn-outline-danger"
          type="button"
          :disabled="assignmentLoading"
          @click="confirmRemove = true"
        >
          {{ t("ux.removeSubject") }}
        </button>
      </div>

      <div v-if="assignmentError" class="alert alert-danger mt-3 mb-0" role="alert">{{ assignmentError }}</div>
      <div v-if="assignmentSuccess" class="alert alert-success mt-3 mb-0" role="status">{{ assignmentSuccess }}</div>
    </section>

    <section v-if="resultsTab" class="surface-card members-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">{{ t("groupDetails.detailedStatistics") }}</h2>
          <span class="pill">{{ statisticsRangeLabel || t("groupDetails.currentRange") }}</span>
        </div>
      </div>

      <div class="statistics-toolbar">
        <div class="statistics-date-controls">
        <label class="field-wrap statistics-period">{{ t('ux.periodEnd') }} <input class="form-control" v-model="statisticsEndDate" type="date" @change="loadDetailedStatistics" /></label>
        <button class="btn btn-outline-primary" @click="statisticsEndDate = new Date().toLocaleDateString('en-CA'); loadDetailedStatistics()">{{ t('ux.toToday') }}</button>
        </div>
        <div class="statistics-toolbar-main">
          <div class="statistics-scale-toggle">
            <button
              v-for="scale in statScales"
              :key="scale.value"
              class="statistics-scale-btn"
              :class="{ active: statisticsScale === scale.value }"
              :aria-pressed="statisticsScale === scale.value"
              type="button"
              :disabled="statisticsLoading"
              @click="setStatisticsScale(scale.value)"
            >
              {{ scale.label }}
            </button>
          </div>
          <button
            class="statistics-sort-toggle"
            type="button"
            :disabled="statisticsLoading"
            @click="toggleStatisticsSort"
          >
            <span>{{ t("groupDetails.sortBy", { mode: statisticsSortLabel }) }}</span>
          </button>
        </div>
        <router-link
          class="btn btn-outline-primary btn-sm"
          :to="{ name: 'group-overview', params: { id: props.id } }"
        >
          {{ t("groupDetails.openScheduleAndResults") }}
        </router-link>
      </div>

      <div class="statistics-legend">
        <span
          v-for="item in statLegend"
          :key="item.state"
          class="statistics-legend-item"
        >
          <span class="statistics-legend-swatch" :class="`state-${item.state}`"></span>
          {{ item.label }}
        </span>
      </div>

      <div v-if="statisticsError" class="alert alert-danger compact-alert" role="alert">
        {{ statisticsError }}
        <button class="btn btn-outline-primary" @click="loadDetailedStatistics">{{ t('ux.retry') }}</button>
      </div>

      <div v-if="statisticsLoading" class="empty-box">
        {{ t("groupDetails.loadingDetailedStatistics") }}
      </div>

      <div v-else-if="!statisticsError && !loadError && group.students.length === 0" class="empty-box">
        {{ t("groupDetails.noStudentsInGroup") }}
      </div>

      <div v-else-if="!statisticsError && !loadError">
        <div v-if="!hasScheduledTests" class="empty-box compact-empty-box">
          {{ t("groupDetails.noScheduledTests") }}
        </div>

        <div class="statistics-mobile">
          <article v-for="row in sortedStatisticsStudents" :key="row.student_id" class="surface-card">
            <h3>{{ row.username }}</h3>
            <template v-for="cell in [...row.cells].reverse()" :key="cell.date">
              <div v-if="cell.tests.length"><strong>{{ formatStatisticsDay(cell.date) }}</strong>
                <p v-for="test in cell.tests" :key="test.schedule_entry_id">
                  {{ test.task_title || test.topic_title }} · {{ formatTestOutcome(test) }}
                  <router-link class="inline-action-link" v-if="test.attempt_id" :to="{name: 'attempt-detail', params: {id: test.attempt_id}}">{{ t('ux.result') }}</router-link>
                </p>
              </div>
            </template>
          </article>
        </div>
        <div ref="statisticsTable" class="statistics-table-wrap" tabindex="0" role="region" :aria-label="t('groupDetails.detailedStatistics')">
          <table class="statistics-table">
            <thead>
              <tr>
                <th class="statistics-student-head">{{ t("groupDetails.studentHeader") }}</th>
                <th
                  v-for="column in statistics.dates"
                  :key="column.date"
                  class="statistics-date-head"
                  :class="{ 'has-tests': column.scheduled_count > 0 }"
                >
                  <span class="statistics-date-weekday">{{ formatStatisticsWeekday(column.date) }}</span>
                  <span class="statistics-date-label">{{ formatStatisticsDay(column.date) }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sortedStatisticsStudents" :key="row.student_id">
                <th class="statistics-student-cell" scope="row">
                  <div class="statistics-student-stack">
                    <div class="member-name">{{ row.username }}</div>
                    <div class="statistics-rank-row">
                      <span class="statistics-rank-label">{{ statisticsRankLabel(row.rank) }}</span>
                      <span
                        v-if="row.rank_trend === 'up'"
                        class="statistics-rank-trend trend-up"
                        :title="t('groupDetails.rankImproved')"
                      >
                        &uarr;
                      </span>
                      <span
                        v-else-if="row.rank_trend === 'down'"
                        class="statistics-rank-trend trend-down"
                        :title="t('groupDetails.rankDropped')"
                      >
                        &darr;
                      </span>
                    </div>
                  </div>
                </th>
                <td
                  v-for="cell in row.cells"
                  :key="`${row.student_id}-${cell.date}`"
                  class="statistics-cell"
                  :class="`state-${cell.state}`"
                >
                  <div v-if="cell.tests.length" class="statistics-test-list">
                    <div
                      v-for="test in cell.tests"
                      :key="test.schedule_entry_id"
                      class="statistics-test-item"
                    >
                      <div class="statistics-test-title">
                        {{ test.task_title || test.topic_title || t("common.task") }}
                      </div>
                      <div
                        class="statistics-test-result"
                        :class="`result-${test.result}`"
                      >
                        {{ formatTestOutcome(test) }}
                        <router-link class="inline-action-link" v-if="test.attempt_id" :to="{name: 'attempt-detail', params:{id:test.attempt_id}}">{{ t("ux.result") }}</router-link>
                      </div>
                    </div>
                  </div>
                  <div v-else class="statistics-empty-mark">-</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section v-if="membersTab" class="surface-card search-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">{{ t("groupDetails.addNewStudent") }}</h2>
          <span class="pill">{{ t("groupDetails.liveSearch") }}</span>
        </div>
      </div>

      <p v-if="!group.can_manage_students" class="alert alert-info">{{ t('ux.noMemberAccess') }}</p>
      <div v-else class="search-column">
        <p class="search-hint">{{ t("groupDetails.searchHint") }}</p>

        <input
          v-model="searchQuery"
          class="form-control search-input"
          type="text"
          :placeholder="t('groupDetails.searchPlaceholder')"
          :aria-label="t('groupDetails.searchPlaceholder')"
        />

        <div v-if="searchLoading" class="search-state">{{ t("groupDetails.searching") }}</div>
        <div v-if="searchError" class="alert alert-danger mt-3 mb-0" role="alert">{{ searchError }}</div>
        <div
          v-if="!searchLoading && searchQuery.trim() && !searchError && searchResults.length === 0"
          class="search-state"
        >
          {{ t("groupDetails.nothingFound") }}
        </div>

        <div v-if="searchResults.length > 0" class="search-results">
          <article
            v-for="student in searchResults"
            :key="student.id"
            class="search-item"
          >
            <div>
              <div class="member-name">{{ student.username }}</div>
              <div class="member-meta">
                {{ t("groupDetails.memberUserMeta", { userId: student.user, studentId: student.id }) }}
              </div>
            </div>

            <div class="search-actions">
              <span v-if="student.in_group" class="badge text-bg-success">
                {{ t("groupDetails.inGroup") }}
              </span>
              <button
                v-else
                class="btn btn-success btn-sm"
                :disabled="addLoadingUserId === student.user"
                type="button"
                @click="addStudentToGroup(student)"
              >
                {{ addLoadingUserId === student.user ? t("groupDetails.adding") : t("common.add") }}
              </button>
            </div>
          </article>
        </div>

        <div v-if="addResultMessage" class="alert alert-info mt-3 mb-0" role="status">{{ addResultMessage }}</div>

      </div>
      <div class="current-students-wrap">
          <div class="column-head current-students-head">
            <h3 class="current-students-title">{{ t("groupDetails.currentStudents") }}</h3>
            <span class="pill">{{ t("common.totalCount", { count: studentCount }) }}</span>
          </div>

          <div v-if="group.students.length === 0" class="empty-box">
            {{ t("groupDetails.noStudentsInGroup") }}
          </div>

          <div v-else class="members-list compact-members-list">
            <article
              v-for="(student, index) in group.students"
              :key="student.id"
              class="member-item"

            >
              <div class="member-index">#{{ index + 1 }}</div>
              <div class="member-info">
                <div class="member-name">{{ student.username || t("common.unknown") }}</div>
                <div class="member-meta">
                  {{ t("groupDetails.memberStudentMeta", { studentId: student.id, userId: student.user }) }}
                </div>
              </div>
              <button
                v-if="group.can_manage_students" class="ghost-danger-btn"
                type="button"
                :disabled="removeLoadingUserId === student.user"
                @click="pendingRemoval = student"
              >
                {{ removeLoadingUserId === student.user ? t("groupDetails.removing") : t("common.remove") }}
              </button>
            </article>
          </div>
      </div>
    </section>
  </div>
</template>

<style scoped src="./GroupDetail.css"></style>
