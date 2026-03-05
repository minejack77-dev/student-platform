<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Attempt, Student } from "@/api.js";

const router = useRouter();

const tasks = ref([]);
const searchQuery = ref("");
const sortMode = ref("topic");
const loadError = ref("");
const actionError = ref("");
const isLoading = ref(false);
const startingTaskKey = ref("");

const sortTasks = (items) => {
  const sorted = [...items];
  if (sortMode.value === "group") {
    sorted.sort((a, b) => a.group_name.localeCompare(b.group_name));
    return sorted;
  }
  sorted.sort((a, b) => a.topic_title.localeCompare(b.topic_title));
  return sorted;
};

const filteredTasks = computed(() => {
  const sorted = sortTasks(tasks.value);
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) {
    return sorted;
  }
  return sorted.filter((task) =>
    [task.topic_title, task.group_name, task.teacher_username]
      .map((value) => (value || "").toLowerCase())
      .some((value) => value.includes(query)),
  );
});

const totalTasks = computed(() => tasks.value.length);
const groupsCount = computed(() => new Set(tasks.value.map((task) => task.group_id)).size);

const loadTasks = async () => {
  isLoading.value = true;
  loadError.value = "";
  actionError.value = "";
  try {
    const response = await Student.meAssignments();
    tasks.value = (response ?? []).map((item, index) => ({
      ...item,
      task_key: `${item.group_id}-${item.topic_id}-${item.teacher_id}-${index}`,
    }));
  } catch (error) {
    loadError.value =
      error?.response?.data?.detail || "Could not load assigned tasks for this account.";
    tasks.value = [];
  } finally {
    isLoading.value = false;
  }
};

const setSortMode = (mode) => {
  sortMode.value = mode;
};

const startTask = async (task) => {
  actionError.value = "";
  startingTaskKey.value = task.task_key;
  try {
    const createdAttempt = await Attempt.save({
      topic: task.topic_id,
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

onMounted(async () => {
  await loadTasks();
});
</script>

<template>
  <div class="student-page">
    <section class="surface-card hero-panel">
      <div class="hero-copy">
        <span class="pill">Workspace</span>
        <h1 class="hero-title">Student Tasks</h1>
        <p class="hero-subtitle">
          Here are the tasks assigned to your groups. Pick one and start attempt.
        </p>
      </div>

      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-label">Tasks</div>
          <div class="stat-value">{{ totalTasks }}</div>
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
      <div class="section-head">
        <div>
          <h2 class="section-title">Assigned Tasks</h2>
          <p class="section-subtitle">Search and start your topic attempts.</p>
        </div>

        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: sortMode === 'topic' }"
              type="button"
              @click="setSortMode('topic')"
            >
              Topic
            </button>
            <button
              class="sort-btn"
              :class="{ active: sortMode === 'group' }"
              type="button"
              @click="setSortMode('group')"
            >
              Group
            </button>
          </div>
          <div class="search-wrap">
            <input
              v-model="searchQuery"
              class="form-control"
              type="text"
              placeholder="Search by topic, group, or teacher"
            />
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="empty-box">Loading tasks...</div>
      <div v-else-if="filteredTasks.length === 0" class="empty-box">No assigned tasks found.</div>

      <div v-else class="cards-grid">
        <article
          v-for="(task, index) in filteredTasks"
          :key="task.task_key"
          class="entity-card"
          :style="{ '--delay': `${index * 45}ms` }"
        >
          <div class="entity-header">
            <h3 class="entity-title">{{ task.topic_title }}</h3>
            <span class="entity-chip">Task</span>
          </div>

          <p class="entity-text">Teacher: {{ task.teacher_username }}</p>
          <div class="assignment-chip">Group: {{ task.group_name }}</div>

          <button
            class="btn btn-primary btn-sm action-btn"
            type="button"
            :disabled="startingTaskKey === task.task_key"
            @click="startTask(task)"
          >
            {{ startingTaskKey === task.task_key ? "Starting..." : "Start task" }}
          </button>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped src="./StudentHomePage.css"></style>
