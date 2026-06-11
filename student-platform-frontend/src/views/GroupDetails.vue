<script setup>
import axios from "axios";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Group, Subject, Workbook } from "@/api.js";

const props = defineProps(["id"]);

const monthDayFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
});
const weekdayFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
});
const longDateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  year: "numeric",
});
const studentNameCollator = new Intl.Collator("en", {
  numeric: true,
  sensitivity: "base",
});

const STAT_SCALES = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "three_months", label: "3 months" },
];

const STAT_LEGEND = [
  { state: "all_correct", label: "All correct" },
  { state: "partial", label: "Partly correct" },
  { state: "none_correct", label: "None correct" },
  { state: "missed", label: "Missed test" },
  { state: "no_test", label: "No test assigned" },
];

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
const statisticsScale = ref("week");
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

const loadGroup = async () => {
  loadError.value = "";
  try {
    const response = await Group.get(props.id);
    group.value = {
      ...response,
      students: response.students ?? [],
    };
  } catch {
    loadError.value = "Failed to load group.";
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
    assignmentError.value =
      error?.response?.data?.detail || "Could not load your assignment.";
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
    });
  } catch (error) {
    statisticsError.value =
      error?.response?.data?.detail ||
      error?.response?.data?.scale ||
      error?.response?.data?.end_date ||
      "Could not load detailed statistics.";
    statistics.value = createEmptyStatistics();
  } finally {
    statisticsLoading.value = false;
  }
};

const saveTeacherAssignment = async () => {
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
      assignmentSuccess.value = "Assignment removed for your profile.";
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
      assignmentSuccess.value = "Assignment saved for your profile.";
    }
    await loadGroup();
  } catch (error) {
    assignmentError.value =
      error?.response?.data?.workbook?.[0] ||
      error?.response?.data?.topic?.[0] ||
      error?.response?.data?.subject?.[0] ||
      error?.response?.data?.detail ||
      "Could not save assignment.";
  } finally {
    assignmentLoading.value = false;
  }
};

const clearTeacherAssignment = async () => {
  assignmentError.value = "";
  assignmentSuccess.value = "";
  assignmentLoading.value = true;
  try {
    await Group.clearTeacherAssignment(props.id);
    assignmentForm.value = { subject: "", workbook: "" };
    savedAssignmentSubject.value = "";
    savedAssignmentWorkbook.value = "";
    workbooks.value = [];
    assignmentSuccess.value = "Assignment removed for your profile.";
    await loadGroup();
  } catch (error) {
    assignmentError.value =
      error?.response?.data?.detail || "Could not remove assignment.";
  } finally {
    assignmentLoading.value = false;
  }
};

const onSubjectChange = async () => {
  assignmentForm.value.workbook = "";
  savedAssignmentWorkbook.value = "";
  assignmentSuccess.value = "";
  await loadWorkbooks(assignmentForm.value.subject);
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
    searchError.value = error?.response?.data?.detail || "Search failed.";
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
      ? "Student added to group."
      : "Student is already in this group.";

    searchResults.value = searchResults.value.map((item) =>
      item.user === student.user ? { ...item, in_group: true } : item,
    );
    await Promise.all([loadGroup(), loadDetailedStatistics()]);
  } catch (error) {
    addResultMessage.value =
      error?.response?.data?.detail || "Could not add student to group.";
  } finally {
    addLoadingUserId.value = null;
  }
};

const removeStudentFromGroup = async (student) => {
  addResultMessage.value = "";
  removeLoadingUserId.value = student.user;
  try {
    const response = await axios.post(`/api/group/${props.id}/remove-student/`, {
      user_id: student.user,
    });

    if (response.data?.removed) {
      addResultMessage.value = "Student removed from group.";
      group.value.students = group.value.students.filter((item) => item.id !== student.id);
      searchResults.value = searchResults.value.map((item) =>
        item.user === student.user ? { ...item, in_group: false } : item,
      );
      await loadDetailedStatistics();
    } else {
      addResultMessage.value = "Student is not in this group.";
    }
  } catch (error) {
    addResultMessage.value =
      error?.response?.data?.detail || "Could not remove student from group.";
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
    loadError.value = "Failed to load group details.";
  }
};

const studentCount = computed(() => group.value.students.length);
const currentSubjectLabel = computed(() => {
  const subjectName = group.value.teacher_assignment?.subject_name;
  const workbookTitle = group.value.teacher_assignment?.workbook_title;
  if (!subjectName) {
    return "Not assigned yet";
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
  return `${longDateFormatter.format(startDate)} - ${longDateFormatter.format(endDate)}`;
});
const hasScheduledTests = computed(() =>
  (statistics.value.dates ?? []).some((column) => column.scheduled_count > 0),
);
const statisticsSortLabel = computed(() =>
  statisticsSortMode.value === "rank" ? "rank" : "name",
);
const sortedStatisticsStudents = computed(() => {
  const rows = [...(statistics.value.students ?? [])];

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
  return date ? monthDayFormatter.format(date) : value;
};

const formatStatisticsWeekday = (value) => {
  const date = parseISODate(value);
  return date ? weekdayFormatter.format(date) : "";
};

const formatTestOutcome = (test) => {
  if (test.result === "missed") {
    return "Missed";
  }
  if (test.correct_count == null || test.total_questions == null) {
    return "No result";
  }
  return `${test.correct_count} / ${test.total_questions}`;
};

const formatStatisticsRank = (rank) => (rank == null ? "Rank —" : `Rank #${rank}`);

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

onBeforeUnmount(() => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
});
</script>

<template>
  <div class="group-page">
    <section class="surface-card group-hero">
      <div class="hero-topline">
        <div class="hero-heading-row">
          <span class="pill">Group Details</span>
          <h1 class="group-title">{{ group.name || "Untitled group" }}</h1>
        </div>
      </div>

      <div class="hero-copy">
        <p class="group-description">{{ group.description || "No description available." }}</p>
      </div>

      <div class="hero-summary-row">
        <div class="hero-meta">
          <div class="meta-card">
            <div class="meta-label">Members</div>
            <div class="meta-value">{{ studentCount }}</div>
          </div>
          <div class="meta-card meta-card-wide">
            <div class="meta-label">Subject</div>
            <div class="meta-value meta-value-small">{{ currentSubjectLabel }}</div>
          </div>
        </div>

        <router-link
          class="hero-link-button hero-link-primary"
          :to="{ name: 'group-overview', params: { id: props.id } }"
        >
          Group Overview
        </router-link>
        <router-link class="home-link hero-link-button hero-link-secondary" to="/">
          Back to dashboard
        </router-link>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section class="surface-card assignment-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">Subject</h2>
          <span class="pill">Personal for your teacher profile</span>
        </div>
      </div>

      <p class="assignment-hint">
        Save the subject and workbook here, then use Group Overview to manage the weekly schedule.
      </p>

      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label">Subject</label>
          <select v-model="assignmentForm.subject" class="form-select" @change="onSubjectChange">
            <option value="">No subject selected</option>
            <option v-for="subject in subjects" :key="subject.id" :value="String(subject.id)">
              {{ subject.name }}
            </option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label">Workbook</label>
          <select v-model="assignmentForm.workbook" class="form-select" :disabled="!assignmentForm.subject">
            <option value="">
              {{ assignmentForm.subject ? "No workbook selected" : "Choose subject first" }}
            </option>
            <option v-for="workbook in workbooks" :key="workbook.id" :value="String(workbook.id)">
              {{ workbook.title }}
            </option>
          </select>
        </div>
      </div>

      <div class="assignment-actions">
        <button class="btn btn-primary" type="button" :disabled="assignmentLoading" @click="saveTeacherAssignment">
          {{ assignmentLoading ? "Saving..." : "Save assignment" }}
        </button>
        <button
          class="btn btn-outline-danger"
          type="button"
          :disabled="assignmentLoading"
          @click="clearTeacherAssignment"
        >
          Remove assignment
        </button>
      </div>

      <div v-if="assignmentError" class="alert alert-danger mt-3 mb-0">{{ assignmentError }}</div>
      <div v-if="assignmentSuccess" class="alert alert-success mt-3 mb-0">{{ assignmentSuccess }}</div>
    </section>

    <section class="surface-card members-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">Detailed Statistics</h2>
          <span class="pill">{{ statisticsRangeLabel || "Current range" }}</span>
        </div>
      </div>

      <div class="statistics-toolbar">
        <div class="statistics-toolbar-main">
          <div class="statistics-scale-toggle">
            <button
              v-for="scale in STAT_SCALES"
              :key="scale.value"
              class="statistics-scale-btn"
              :class="{ active: statisticsScale === scale.value }"
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
            <span>Sort by {{ statisticsSortLabel }}</span>
          </button>
        </div>
        <router-link
          class="btn btn-outline-primary btn-sm"
          :to="{ name: 'group-overview', params: { id: props.id } }"
        >
          Open schedule and results
        </router-link>
      </div>

      <div class="statistics-legend">
        <span
          v-for="item in STAT_LEGEND"
          :key="item.state"
          class="statistics-legend-item"
        >
          <span class="statistics-legend-swatch" :class="`state-${item.state}`"></span>
          {{ item.label }}
        </span>
      </div>

      <div v-if="statisticsError" class="alert alert-danger compact-alert">
        {{ statisticsError }}
      </div>

      <div v-if="statisticsLoading" class="empty-box">Loading detailed statistics...</div>

      <div v-else-if="group.students.length === 0" class="empty-box">
        No students in this group yet.
      </div>

      <div v-else>
        <div v-if="!hasScheduledTests" class="empty-box compact-empty-box">
          No scheduled tests were found in the selected range yet.
        </div>

        <div class="statistics-table-wrap">
          <table class="statistics-table">
            <thead>
              <tr>
                <th class="statistics-student-head">Student</th>
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
                      <span class="statistics-rank-label">{{ formatStatisticsRank(row.rank) }}</span>
                      <span
                        v-if="row.rank_trend === 'up'"
                        class="statistics-rank-trend trend-up"
                        title="Rank improved"
                      >
                        &uarr;
                      </span>
                      <span
                        v-else-if="row.rank_trend === 'down'"
                        class="statistics-rank-trend trend-down"
                        title="Rank dropped"
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
                        {{ test.task_title || test.topic_title || "Task" }}
                      </div>
                      <div
                        class="statistics-test-result"
                        :class="`result-${test.result}`"
                      >
                        {{ formatTestOutcome(test) }}
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

    <section class="surface-card search-panel">
      <div class="panel-header">
        <div class="column-head panel-head">
          <h2 class="section-title">Add New Student</h2>
          <span class="pill">Live search</span>
        </div>
      </div>

      <div class="search-column">
        <p class="search-hint">Type user id or username, then add in one click.</p>

        <input v-model="searchQuery" class="form-control search-input" type="text" placeholder="e.g. 42 or alex" />

        <div v-if="searchLoading" class="search-state">Searching...</div>
        <div v-if="searchError" class="alert alert-danger mt-3 mb-0">{{ searchError }}</div>
        <div
          v-if="!searchLoading && searchQuery.trim() && !searchError && searchResults.length === 0"
          class="search-state"
        >
          Nothing found.
        </div>

        <div v-if="searchResults.length > 0" class="search-results">
          <article
            v-for="student in searchResults"
            :key="student.id"
            class="search-item"
          >
            <div>
              <div class="member-name">{{ student.username }}</div>
              <div class="member-meta">user id: {{ student.user }}, student id: {{ student.id }}</div>
            </div>

            <div class="search-actions">
              <span v-if="student.in_group" class="badge text-bg-success">In group</span>
              <button
                v-else
                class="btn btn-success btn-sm"
                :disabled="addLoadingUserId === student.user"
                type="button"
                @click="addStudentToGroup(student)"
              >
                {{ addLoadingUserId === student.user ? "Adding..." : "Add" }}
              </button>
            </div>
          </article>
        </div>

        <div v-if="addResultMessage" class="alert alert-info mt-3 mb-0">{{ addResultMessage }}</div>

        <div class="current-students-wrap">
          <div class="column-head current-students-head">
            <h3 class="current-students-title">Current Students</h3>
            <span class="pill">{{ studentCount }} total</span>
          </div>

          <div v-if="group.students.length === 0" class="empty-box">
            No students in this group yet.
          </div>

          <div v-else class="members-list compact-members-list">
            <article
              v-for="(student, index) in group.students"
              :key="student.id"
              class="member-item"
              :style="{ '--delay': `${index * 32}ms` }"
            >
              <div class="member-index">#{{ index + 1 }}</div>
              <div class="member-info">
                <div class="member-name">{{ student.username || "Unknown" }}</div>
                <div class="member-meta">student id: {{ student.id }}, user id: {{ student.user }}</div>
              </div>
              <button
                class="ghost-danger-btn"
                type="button"
                :disabled="removeLoadingUserId === student.user"
                @click="removeStudentFromGroup(student)"
              >
                {{ removeLoadingUserId === student.user ? "Removing..." : "Remove" }}
              </button>
            </article>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped src="./GroupDetail.css"></style>
