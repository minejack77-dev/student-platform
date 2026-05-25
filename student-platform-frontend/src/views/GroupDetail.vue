<script setup>
import axios from "axios";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Group, Subject, Task } from "@/api.js";

const props = defineProps(["id"]);

const WEEK_LENGTH = 7;
const dayNameFormatter = new Intl.DateTimeFormat("en-US", { weekday: "short" });
const dayNumberFormatter = new Intl.DateTimeFormat("en-US", { day: "numeric" });
const monthDayFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
});
const monthRangeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
});
const fullDateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});

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
  taskDraft: "",
});

const normalizeCalendarEntry = (item) => ({
  ...item,
  clientKey: item.id ? `entry-${item.id}` : `empty-${item.date}`,
  topic: item.topic ?? null,
  task: item.task ?? null,
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

const group = ref({ students: [] });
const loadError = ref("");
const rankingByStudentId = ref({});

const subjects = ref([]);
const tasks = ref([]);
const assignmentForm = ref({
  subject: "",
  topic: "",
});
const savedAssignmentSubject = ref("");
const assignmentLoading = ref(false);
const assignmentError = ref("");
const assignmentSuccess = ref("");

const calendarStartDate = ref(formatISODate(startOfWeek(new Date())));
const calendarDays = ref([]);
const calendarLoading = ref(false);
const calendarError = ref("");
const calendarMessage = ref("");
const calendarSavingKey = ref("");

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

const loadRanking = async () => {
  try {
    const response = await Group.getRanking(props.id);
    const map = {};
    for (const row of response.ranking ?? []) {
      map[row.student_id] = row;
    }
    rankingByStudentId.value = map;
  } catch {
    rankingByStudentId.value = {};
  }
};

const loadSubjects = async () => {
  const response = await Subject.filter({ is_active: true, ordering: "name" });
  subjects.value = response.results ?? response;
};

const loadTasksBySubject = async (subjectId) => {
  if (!subjectId) {
    tasks.value = [];
    return;
  }
  const response = await Task.filter({
    subject: subjectId,
    is_active: true,
    ordering: "title",
  });
  tasks.value = response.results ?? response;
};

const loadTeacherAssignment = async () => {
  assignmentError.value = "";
  try {
    const assignment = await Group.getTeacherAssignment(props.id);
    assignmentForm.value.subject = assignment.subject ? String(assignment.subject) : "";
    assignmentForm.value.topic = assignment.topic ? String(assignment.topic) : "";
    savedAssignmentSubject.value = assignmentForm.value.subject;
    await loadTasksBySubject(assignmentForm.value.subject);
  } catch (error) {
    assignmentError.value =
      error?.response?.data?.detail || "Could not load your assignment.";
    assignmentForm.value.subject = "";
    assignmentForm.value.topic = "";
    savedAssignmentSubject.value = "";
    tasks.value = [];
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
  } catch (error) {
    calendarError.value =
      error?.response?.data?.detail || "Could not load the topic calendar.";
    calendarDays.value = [];
  } finally {
    calendarLoading.value = false;
  }
};

const saveTeacherAssignment = async () => {
  assignmentError.value = "";
  assignmentSuccess.value = "";
  calendarMessage.value = "";
  assignmentLoading.value = true;
  try {
    const subjectId = assignmentForm.value.subject
      ? Number(assignmentForm.value.subject)
      : null;
      if (!subjectId) {
        await Group.clearTeacherAssignment(props.id);
        assignmentForm.value.subject = "";
        assignmentForm.value.topic = "";
        savedAssignmentSubject.value = "";
        tasks.value = [];
        calendarDays.value = [];
        assignmentSuccess.value = "Assignment cleared for your profile.";
      } else {
        await Group.saveTeacherAssignment(props.id, {
          subject: subjectId,
          topic: null,
          task: null,
        });
        savedAssignmentSubject.value = String(subjectId);
        assignmentSuccess.value = "Assignment saved for your profile.";
        await Promise.all([loadTasksBySubject(subjectId), loadTopicCalendar()]);
    }
    await loadGroup();
  } catch (error) {
    assignmentError.value =
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
  calendarMessage.value = "";
  assignmentLoading.value = true;
  try {
    await Group.clearTeacherAssignment(props.id);
    assignmentForm.value.subject = "";
    assignmentForm.value.topic = "";
    savedAssignmentSubject.value = "";
    tasks.value = [];
    calendarDays.value = [];
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
  assignmentForm.value.topic = "";
  assignmentSuccess.value = "";
  calendarMessage.value = "";
  await loadTasksBySubject(assignmentForm.value.subject);
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
    calendarMessage.value = `${response.task_title || response.topic_title} saved for ${fullDateFormatter.format(parseISODate(day.date))}.`;
  } catch (error) {
    calendarError.value =
      error?.response?.data?.task?.[0] ||
      error?.response?.data?.detail ||
      "Could not save this date.";
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
    calendarMessage.value = `Task removed from ${fullDateFormatter.format(parseISODate(day.date))}.`;
  } catch (error) {
    calendarError.value =
      error?.response?.data?.detail || "Could not clear this date.";
  } finally {
    calendarSavingKey.value = "";
  }
};

const studentCount = computed(() => group.value.students.length);
const scheduleUnlocked = computed(
  () =>
    Boolean(savedAssignmentSubject.value) &&
    assignmentForm.value.subject === savedAssignmentSubject.value,
);
const scheduleSubjectName = computed(() => {
  return (
    subjects.value.find((subject) => String(subject.id) === savedAssignmentSubject.value)
      ?.name || "No subject"
  );
});
const scheduleDisabledMessage = computed(() => {
  if (!assignmentForm.value.subject) {
    return "Choose a subject first. The weekly calendar uses that subject as its task pool.";
  }
  if (!savedAssignmentSubject.value) {
    return "Save the subject above first, then the weekly calendar will unlock.";
  }
  if (assignmentForm.value.subject !== savedAssignmentSubject.value) {
    return "You changed the subject. Save it first so the weekly calendar can refresh safely.";
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
  return `${monthRangeFormatter.format(first)} • ${monthDayFormatter.format(first)} - ${monthDayFormatter.format(last)}`;
});

const isCalendarTaskDirty = (item) =>
  (item.task ? String(item.task) : "") !== String(item.taskDraft || "");
const isToday = (value) => formatISODate(new Date()) === value;
const isWeekend = (value) => {
  const date = parseISODate(value);
  const day = date?.getDay();
  return day === 0 || day === 6;
};
const formatDayName = (value) => dayNameFormatter.format(parseISODate(value));
const formatDayNumber = (value) => dayNumberFormatter.format(parseISODate(value));
const formatMonthDay = (value) => monthDayFormatter.format(parseISODate(value));

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

    if (response.data?.added) {
      addResultMessage.value = "Student added to group.";
    } else {
      addResultMessage.value = "Student is already in this group.";
    }

    searchResults.value = searchResults.value.map((item) =>
      item.user === student.user ? { ...item, in_group: true } : item,
    );
    await loadGroup();
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

watch(
  () => props.id,
  async () => {
    searchQuery.value = "";
    searchResults.value = [];
    searchError.value = "";
    addResultMessage.value = "";
    addLoadingUserId.value = null;
    removeLoadingUserId.value = null;
    assignmentError.value = "";
    assignmentSuccess.value = "";
    assignmentForm.value = { subject: "", topic: "" };
    savedAssignmentSubject.value = "";
    tasks.value = [];
    calendarDays.value = [];
    calendarError.value = "";
    calendarMessage.value = "";
    calendarStartDate.value = formatISODate(startOfWeek(new Date()));
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
    await Promise.all([loadGroup(), loadSubjects(), loadRanking()]);
    await loadTeacherAssignment();
    await loadTopicCalendar();
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
  await Promise.all([loadGroup(), loadSubjects(), loadRanking()]);
  await loadTeacherAssignment();
  await loadTopicCalendar();
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
      <div>
        <span class="pill">Group</span>
        <h1 class="group-title">{{ group.name || "Untitled group" }}</h1>
        <p class="group-description">{{ group.description || "No description available." }}</p>
      </div>

      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">Members</div>
          <div class="meta-value">{{ studentCount }}</div>
        </div>
        <router-link class="home-link" to="/">Back to dashboard</router-link>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section class="surface-card assignment-panel">
      <div class="column-head">
        <h2 class="section-title">Your Assignment In This Group</h2>
        <span class="pill">Personal for your teacher profile</span>
      </div>
      <p class="assignment-hint">
        Save the subject once, then use the weekly calendar below to assign a different topic to each date.
      </p>

      <div class="row g-3">
        <div class="col-md-12">
          <label class="form-label">Subject</label>
          <select v-model="assignmentForm.subject" class="form-select" @change="onSubjectChange">
            <option value="">No subject selected</option>
            <option v-for="subject in subjects" :key="subject.id" :value="String(subject.id)">
              {{ subject.name }}
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

    <section class="surface-card schedule-panel">
      <div class="schedule-header">
        <div>
          <div class="column-head schedule-head">
            <h2 class="section-title">Weekly Task Calendar</h2>
            <span class="pill">{{ calendarAssignedCount }} tasks scheduled</span>
          </div>
          <p class="assignment-hint schedule-hint">
            Move week by week and pin the exact task for each lesson date.
          </p>
        </div>

        <div class="calendar-toolbar">
          <button class="btn btn-outline-primary btn-sm" type="button" @click="shiftCalendarWeek(-1)">
            Previous week
          </button>
          <button class="btn btn-outline-primary btn-sm" type="button" @click="jumpToCurrentWeek">
            Current week
          </button>
          <button class="btn btn-outline-primary btn-sm" type="button" @click="shiftCalendarWeek(1)">
            Next week
          </button>
        </div>
      </div>

      <div class="schedule-summary">
        <div class="schedule-range">{{ calendarRangeLabel || "Pick a week" }}</div>
        <div class="schedule-subject">
          Task pool:
          <strong>{{ scheduleUnlocked ? scheduleSubjectName : "locked until subject is saved" }}</strong>
        </div>
      </div>

      <div v-if="calendarError" class="alert alert-danger mt-3 mb-0">{{ calendarError }}</div>
      <div v-if="calendarMessage" class="alert alert-success mt-3 mb-0">{{ calendarMessage }}</div>

      <div v-if="calendarLoading" class="empty-box schedule-empty mt-3">Loading weekly schedule...</div>

      <div v-else-if="scheduleDisabledMessage" class="schedule-empty">
        <div class="schedule-empty-title">Calendar is waiting for a saved subject</div>
        <p class="schedule-empty-copy">{{ scheduleDisabledMessage }}</p>
      </div>

      <div v-else-if="tasks.length === 0" class="schedule-empty">
        <div class="schedule-empty-title">No active tasks found</div>
        <p class="schedule-empty-copy">
          This subject has no active tasks yet. Add tasks in a topic page, then come back here.
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
              <label class="form-label schedule-label">Task</label>
              <select
                v-model="item.taskDraft"
                class="form-select form-select-sm schedule-select"
                :aria-label="`Task for ${day.date}`"
              >
                <option value="">No task scheduled</option>
                <option v-for="taskItem in tasks" :key="taskItem.id" :value="String(taskItem.id)">
                  {{ taskItem.topic_title }} - {{ taskItem.title }}
                </option>
              </select>

              <div class="schedule-topic-state">
                <span class="schedule-topic-caption">Current</span>
                <strong>{{ item.task_title || item.topic_title || "Free slot" }}</strong>
              </div>

              <div class="schedule-day-actions">
                <button
                  class="btn btn-primary btn-sm"
                  type="button"
                  :disabled="calendarSavingKey === item.clientKey || !item.taskDraft || !isCalendarTaskDirty(item)"
                  @click="saveCalendarTask(day, item)"
                >
                  {{ calendarSavingKey === item.clientKey ? "Saving..." : "Save" }}
                </button>
                <button
                  class="btn btn-outline-secondary btn-sm"
                  type="button"
                  :disabled="calendarSavingKey === item.clientKey || (!item.id && day.items.length === 1 && !item.taskDraft)"
                  @click="clearCalendarTask(day, item)"
                >
                  Clear
                </button>
              </div>
            </article>
          </div>

          <button class="btn btn-outline-primary btn-sm add-task-btn" type="button" @click="addCalendarTask(day)">
            Add another task
          </button>
        </article>
      </div>
    </section>

    <section class="surface-card group-layout">
      <div class="members-column">
        <div class="column-head">
          <h2 class="section-title">Group Members</h2>
          <span class="pill">{{ studentCount }} students</span>
        </div>

        <div v-if="group.students.length === 0" class="empty-box">
          No students in this group yet.
        </div>

        <div v-else class="members-list">
          <article
            v-for="(student, index) in group.students"
            :key="student.id"
            class="member-item"
            :style="{ '--delay': `${index * 38}ms` }"
          >
            <div class="member-index">#{{ index + 1 }}</div>
            <div class="member-info">
              <div class="member-name">{{ student.username || "Unknown" }}</div>
              <div class="member-meta">
                rank: {{ rankingByStudentId[student.id]?.rank ?? "—" }}
              </div>
            </div>
            <div class="member-last-result">
              <div class="member-result-label">Today's results</div>
              <div
                v-if="rankingByStudentId[student.id]?.today_results?.length"
                class="member-results-list"
              >
                <div
                  v-for="result in rankingByStudentId[student.id].today_results"
                  :key="result.schedule_entry_id"
                  class="member-result-item"
                >
                  <span class="member-result-task">
                    {{ result.task_title || result.topic_title || "Task" }}
                  </span>
                  <span
                    v-if="result.result"
                    class="entity-chip"
                    :class="result.result === 'success' ? 'chip-success' : 'chip-fail'"
                  >
                    {{ result.correct_count }} / {{ result.total_questions }}
                  </span>
                  <span v-else class="member-result-placeholder">No result yet</span>
                </div>
              </div>
              <span v-else class="member-result-placeholder">No tests today</span>
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

      <div class="search-column">
        <div class="column-head">
          <h2 class="section-title">Add Student</h2>
          <span class="pill">Live search</span>
        </div>
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
      </div>
    </section>
  </div>
</template>

<style scoped src="./GroupDetail.css"></style>
