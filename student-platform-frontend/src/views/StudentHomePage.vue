<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Attempt, Student } from "@/api.js";

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
  if (!item.date || item.date < today) return "missed";
  if (item.date > today) return "upcoming";
  return "available";
};

const passingThreshold = 8;
const totalQuestions = 10;

const completedItems = computed(() =>
  statsItems.value.filter((i) => i.attempt_status === "completed"),
);
const missedItems = computed(() =>
  statsItems.value.filter((i) => getItemState(i) === "missed"),
);
const completedCount = computed(() => completedItems.value.length + missedItems.value.length);
const passedCount = computed(
  () => completedItems.value.filter((i) => i.result_outcome === "success").length,
);

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
      task_key: `${day.date}-${item.group_id}-${item.topic_id}-${item.teacher_id}-${index}`,
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
      error?.response?.data?.detail || "Could not load assigned tasks for this account.";
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
      error?.response?.data?.topic?.[0] ||
      error?.response?.data?.detail ||
      "Could not start the task.";
  } finally {
    startingTaskKey.value = "";
  }
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
    return "Success";
  }
  if (state === "fail") {
    return "Fail";
  }
  if (state === "in_progress") {
    return "In progress";
  }
  if (state === "expired") {
    return "Window closed";
  }
  if (state === "missed") {
    return "Missed";
  }
  if (state === "upcoming") {
    return "Locked";
  }
  return "Available today";
};

const getTaskStateCopy = (task, date) => {
  const state = getTaskState(task, date);
  if (state === "success" || state === "fail") {
    return `${task.correct_count ?? 0}/${task.total_questions ?? 0} correct`;
  }
  if (state === "in_progress") {
    return "You already started this test today. Continue the same attempt.";
  }
  if (state === "expired") {
    return "This attempt was not finished on the scheduled day.";
  }
  if (state === "missed") {
    return "The scheduled day has passed. This test can no longer be completed.";
  }
  if (state === "upcoming") {
    return `Available on ${monthDayFormatter.format(parseISODate(date))}.`;
  }
  return "You can take this test today.";
};

const getTaskButtonLabel = (task, date) => {
  const state = getTaskState(task, date);
  if (state === "in_progress") {
    return "Continue task";
  }
  if (state === "available") {
    return "Start task";
  }
  return "Unavailable";
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
      [task.topic_title, task.group_name, task.teacher_username, task.subject_name]
        .map((value) => (value || "").toLowerCase())
        .some((value) => value.includes(query)),
    ),
  }));
});

const totalTasks = computed(() =>
  calendarDays.value.reduce((sum, day) => sum + day.items.length, 0),
);
const filteredTaskCount = computed(() =>
  filteredCalendarDays.value.reduce((sum, day) => sum + day.items.length, 0),
);
const groupsCount = computed(() => {
  const groups = new Set();
  for (const day of calendarDays.value) {
    for (const task of day.items) {
      groups.add(task.group_id);
    }
  }
  return groups.size;
});
const activeDatesCount = computed(
  () => calendarDays.value.filter((day) => day.items.length > 0).length,
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

const isToday = (value) => formatISODate(new Date()) === value;
const isWeekend = (value) => {
  const date = parseISODate(value);
  const day = date?.getDay();
  return day === 0 || day === 6;
};
const formatDayName = (value) => dayNameFormatter.format(parseISODate(value));
const formatDayNumber = (value) => dayNumberFormatter.format(parseISODate(value));
const formatMonthDay = (value) => monthDayFormatter.format(parseISODate(value));

onMounted(async () => {
  await Promise.all([loadSchedule(), loadStats()]);
});
</script>

<template>
  <div class="student-page">
    <section class="surface-card hero-panel">
      <div class="hero-copy">
        <span class="pill">Workspace</span>
        <h1 class="hero-title">Student Schedule</h1>
        <p class="hero-subtitle">
          See your weekly topics by date and start the assigned task right from the calendar.
        </p>
      </div>

      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-label">Tasks This Week</div>
          <div class="stat-value">{{ totalTasks }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Active Dates</div>
          <div class="stat-value">{{ activeDatesCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Groups</div>
          <div class="stat-value">{{ groupsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>
    <div v-if="actionError" class="alert alert-danger">{{ actionError }}</div>

    <section class="surface-card section-card">
      <div class="schedule-header">
        <div>
          <div class="column-head schedule-head">
            <h2 class="section-title">Weekly Task Calendar</h2>
            <span class="pill">{{ filteredTaskCount }} visible tasks</span>
          </div>
          <p class="section-subtitle">
            Your teachers can schedule different topics on different dates. This week is shown below.
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
        <div class="search-wrap">
          <input
            v-model="searchQuery"
            class="form-control"
            type="text"
            placeholder="Search by topic, group, subject, or teacher"
          />
        </div>
      </div>

      <div v-if="isLoading" class="empty-box schedule-empty mt-3">Loading weekly schedule...</div>
      <div v-else-if="calendarDays.length === 0" class="empty-box schedule-empty mt-3">No schedule data found.</div>
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

          <div v-if="day.items.length === 0" class="schedule-empty-card">
            {{ searchQuery.trim() ? "No matching tasks for this day." : "No tasks scheduled." }}
          </div>

          <div v-else class="day-task-list">
            <article
              v-for="task in day.items"
              :key="task.task_key"
              class="day-task-item"
              :class="`state-${getTaskState(task, day.date)}`"
            >
              <div class="day-task-head">
                <h3 class="day-task-title">{{ task.topic_title }}</h3>
                <span class="entity-chip" :class="`chip-${getTaskState(task, day.date)}`">
                  {{ getTaskStateLabel(task, day.date) }}
                </span>
              </div>

              <div class="day-task-meta">{{ task.subject_name }}</div>
              <div class="assignment-chip">Group: {{ task.group_name }}</div>
              <div class="day-task-meta">Teacher: {{ task.teacher_username }}</div>
              <div class="task-status-copy">{{ getTaskStateCopy(task, day.date) }}</div>

              <button
                class="btn btn-primary btn-sm action-btn"
                type="button"
                :disabled="startingTaskKey === task.task_key || !canStartOrContinueTask(task, day.date)"
                @click="startTask(task)"
              >
                {{ startingTaskKey === task.task_key ? "Opening..." : getTaskButtonLabel(task, day.date) }}
              </button>
            </article>
          </div>
        </article>
      </div>
    </section>

    <section class="surface-card section-card stats-section">
      <h2 class="section-title">Statistics</h2>
      <div v-if="statsLoading" class="empty-box mt-2">Loading statistics...</div>
      <template v-else>
        <div class="stats-grid">
          <div class="stats-row">
            <span class="stats-label">Completed tasks (this trimester)</span>
            <span class="stats-value">{{ completedCount }}</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">Passed</span>
            <span class="stats-value">{{ passedCount }}</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">Required for credit</span>
            <span class="stats-value stats-future">In future</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">Rating</span>
            <span class="stats-value stats-future">In future</span>
          </div>
        </div>

        <div v-if="statsItems.length === 0" class="empty-box mt-3">No assigned tests.</div>
        <table v-else class="stats-table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Subject</th>
              <th>Date</th>
              <th>Correct</th>
              <th>Required</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in statsItems" :key="item.schedule_entry_id">
              <td>{{ item.topic_title }}</td>
              <td>{{ item.subject_name }}</td>
              <td>{{ item.date ?? "—" }}</td>
              <td>
                <template v-if="item.attempt_status === 'completed'">
                  {{ item.correct_count }} / {{ item.total_questions }}
                </template>
                <span v-else class="stats-na">—</span>
              </td>
              <td>{{ passingThreshold }} / {{ totalQuestions }}</td>
              <td>
                <span class="entity-chip" :class="`chip-${getItemState(item)}`">
                  {{ {
                    success: "Passed",
                    fail: "Failed",
                    in_progress: "In Progress",
                    expired: "Expired",
                    missed: "Missed",
                    upcoming: "Upcoming",
                    available: "Available",
                  }[getItemState(item)] }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </template>
    </section>
  </div>
</template>

<style scoped src="./StudentHomePage.css"></style>
