<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Group, Subject, Topic } from "@/api.js";

const props = defineProps(["id"]);

const subject = ref({});
const groups = ref([]);
const topics = ref([]);
const loadError = ref("");
const assignError = ref("");
const assignSuccess = ref("");
const assignLoadingByGroup = ref({});
const selectedTopicByGroup = ref({});
const selectedGroupToAssign = ref("");

const createTopicForm = ref({
  title: "",
  description: "",
  is_active: true,
});
const createTopicLoading = ref(false);
const createTopicError = ref("");

const numericSubjectId = computed(() => Number(props.id));

const assignedGroups = computed(() =>
  groups.value.filter((group) => group.teacher_assignment?.subject === numericSubjectId.value),
);

const availableGroups = computed(() =>
  groups.value.filter((group) => group.teacher_assignment?.subject !== numericSubjectId.value),
);

const loadSubject = async () => {
  const response = await Subject.get(props.id);
  subject.value = response;
};

const loadTopics = async () => {
  const response = await Topic.filter({
    subject: props.id,
    ordering: "title",
  });
  topics.value = response.results ?? response;
};

const loadGroups = async () => {
  const response = await Group.filter({ ordering: "name" });
  const groupItems = response.results ?? response;
  groups.value = groupItems;

  const nextSelectedTopics = {};
  for (const group of groupItems) {
    if (group.teacher_assignment?.subject === numericSubjectId.value) {
      nextSelectedTopics[group.id] = group.teacher_assignment.topic ?? "";
    }
  }
  selectedTopicByGroup.value = nextSelectedTopics;
};

const loadSubjectPage = async () => {
  loadError.value = "";
  assignError.value = "";
  assignSuccess.value = "";
  try {
    await Promise.all([loadSubject(), loadTopics(), loadGroups()]);
  } catch {
    loadError.value = "Failed to load subject page.";
  }
};

const resetCreateTopicForm = () => {
  createTopicForm.value = {
    title: "",
    description: "",
    is_active: true,
  };
  createTopicError.value = "";
};

const createTopic = async () => {
  createTopicError.value = "";
  if (!createTopicForm.value.title.trim()) {
    createTopicError.value = "Topic title is required.";
    return;
  }

  createTopicLoading.value = true;
  try {
    await Topic.save({
      subject: numericSubjectId.value,
      title: createTopicForm.value.title.trim(),
      description: createTopicForm.value.description.trim(),
      is_active: createTopicForm.value.is_active,
    });
    resetCreateTopicForm();
    await loadTopics();
  } catch (error) {
    createTopicError.value =
      error?.response?.data?.title?.[0] || "Could not create topic.";
  } finally {
    createTopicLoading.value = false;
  }
};

const setGroupLoading = (groupId, loading) => {
  assignLoadingByGroup.value = {
    ...assignLoadingByGroup.value,
    [groupId]: loading,
  };
};

const assignSubjectToGroup = async (groupId) => {
  assignError.value = "";
  assignSuccess.value = "";
  setGroupLoading(groupId, true);
  try {
    await Group.saveTeacherAssignment(groupId, {
      subject: numericSubjectId.value,
      topic: null,
    });
    assignSuccess.value = "Subject assigned to group.";
    await loadGroups();
  } catch (error) {
    assignError.value = error?.response?.data?.detail || "Could not assign subject.";
  } finally {
    setGroupLoading(groupId, false);
  }
};

const assignSelectedGroup = async () => {
  if (!selectedGroupToAssign.value) {
    return;
  }
  await assignSubjectToGroup(Number(selectedGroupToAssign.value));
  selectedGroupToAssign.value = "";
};

const saveTopicForGroup = async (groupId) => {
  assignError.value = "";
  assignSuccess.value = "";
  setGroupLoading(groupId, true);
  try {
    const topicId = selectedTopicByGroup.value[groupId] || null;
    await Group.saveTeacherAssignment(groupId, {
      subject: numericSubjectId.value,
      topic: topicId ? Number(topicId) : null,
    });
    assignSuccess.value = "Group assignment updated.";
    await loadGroups();
  } catch (error) {
    assignError.value =
      error?.response?.data?.detail || "Could not update topic for group.";
  } finally {
    setGroupLoading(groupId, false);
  }
};

const clearSubjectFromGroup = async (groupId) => {
  assignError.value = "";
  assignSuccess.value = "";
  setGroupLoading(groupId, true);
  try {
    await Group.clearTeacherAssignment(groupId);
    assignSuccess.value = "Subject removed from group.";
    await loadGroups();
  } catch (error) {
    assignError.value =
      error?.response?.data?.detail || "Could not remove subject from group.";
  } finally {
    setGroupLoading(groupId, false);
  }
};

watch(
  () => props.id,
  async () => {
    resetCreateTopicForm();
    selectedGroupToAssign.value = "";
    assignError.value = "";
    assignSuccess.value = "";
    await loadSubjectPage();
  },
);

onMounted(async () => {
  await loadSubjectPage();
});
</script>

<template>
  <div class="subject-page">
    <section class="surface-card subject-hero">
      <div>
        <span class="pill">Subject</span>
        <h1 class="subject-title">{{ subject.name || "Untitled subject" }}</h1>
        <p class="subject-description">{{ subject.description || "No description yet." }}</p>
      </div>

      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">Topics</div>
          <div class="meta-value">{{ topics.length }}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">Groups assigned to you</div>
          <div class="meta-value">{{ assignedGroups.length }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>
    <div v-if="assignError" class="alert alert-danger">{{ assignError }}</div>
    <div v-if="assignSuccess" class="alert alert-success">{{ assignSuccess }}</div>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Groups In This Subject</h2>
        <span class="pill">{{ assignedGroups.length }} groups</span>
      </div>

      <div v-if="assignedGroups.length === 0" class="empty-box">
        You have not assigned this subject to any group yet.
      </div>

      <div class="cards-grid">
        <article
          v-for="group in assignedGroups"
          :key="group.id"
          class="group-card"
        >
          <div class="group-card-head">
            <h3 class="group-name">{{ group.name }}</h3>
            <router-link
              class="small-link"
              :to="{ name: 'group-detail', params: { id: group.id } }"
            >
              Open group
            </router-link>
          </div>

          <p class="group-description">{{ group.description || "No description" }}</p>

          <label class="form-label mb-1">Topic for this group</label>
          <select
            v-model="selectedTopicByGroup[group.id]"
            class="form-select form-select-sm"
          >
            <option value="">No topic selected</option>
            <option v-for="topic in topics" :key="topic.id" :value="topic.id">
              {{ topic.title }}
            </option>
          </select>

          <div class="group-actions">
            <button
              class="btn btn-primary btn-sm"
              type="button"
              :disabled="assignLoadingByGroup[group.id]"
              @click="saveTopicForGroup(group.id)"
            >
              {{ assignLoadingByGroup[group.id] ? "Saving..." : "Save topic" }}
            </button>
            <button
              class="btn btn-outline-danger btn-sm"
              type="button"
              :disabled="assignLoadingByGroup[group.id]"
              @click="clearSubjectFromGroup(group.id)"
            >
              Remove subject
            </button>
          </div>
        </article>
      </div>

      <div class="assign-row">
        <div class="assign-copy">
          <h3 class="assign-title">Assign this subject to a group</h3>
          <p class="assign-hint">
            If group already has your assignment, it will be replaced with this subject.
          </p>
        </div>
        <div class="assign-controls">
          <select v-model="selectedGroupToAssign" class="form-select">
            <option value="">Choose group</option>
            <option v-for="group in availableGroups" :key="group.id" :value="group.id">
              {{ group.name }}
            </option>
          </select>
          <button class="btn btn-outline-primary" type="button" @click="assignSelectedGroup">
            Assign subject
          </button>
        </div>
      </div>
    </section>

    <section class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">Topics In Subject</h2>
        <span class="pill">{{ topics.length }} total</span>
      </div>

      <div class="create-topic-box">
        <h3 class="create-title">Create Topic</h3>
        <input
          v-model="createTopicForm.title"
          class="form-control form-control-sm"
          type="text"
          placeholder="Topic title"
        />
        <textarea
          v-model="createTopicForm.description"
          class="form-control form-control-sm"
          rows="2"
          placeholder="Description"
        />
        <div class="form-check">
          <input id="topic-active" v-model="createTopicForm.is_active" class="form-check-input" type="checkbox" />
          <label class="form-check-label" for="topic-active">Active</label>
        </div>
        <div v-if="createTopicError" class="small text-danger">{{ createTopicError }}</div>
        <button class="btn btn-primary btn-sm" type="button" :disabled="createTopicLoading" @click="createTopic">
          {{ createTopicLoading ? "Creating..." : "Create topic" }}
        </button>
      </div>

      <div v-if="topics.length === 0" class="empty-box">No topics in this subject yet.</div>

      <div class="cards-grid">
        <article
          v-for="topic in topics"
          :key="topic.id"
          class="topic-card"
        >
          <div class="group-card-head">
            <h3 class="group-name">{{ topic.title }}</h3>
            <router-link
              class="small-link"
              :to="{ name: 'topic-detail', params: { id: topic.id } }"
            >
              Open topic
            </router-link>
          </div>
          <p class="group-description">{{ topic.description || "No description" }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.subject-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.subject-hero {
  align-items: end;
  animation: rise-fade 430ms ease both;
  background:
    radial-gradient(circle at 86% 22%, rgba(31, 95, 216, 0.2), transparent 46%),
    linear-gradient(130deg, rgba(255, 255, 255, 0.9) 0%, rgba(244, 250, 255, 0.96) 100%);
  display: grid;
  gap: 16px;
  grid-template-columns: 1.2fr 0.8fr;
  padding: 22px;
}

.subject-title {
  font-size: clamp(28px, 3.8vw, 38px);
  margin: 10px 0 6px;
}

.subject-description {
  color: var(--ink-soft);
  margin: 0;
  max-width: 680px;
}

.hero-meta {
  display: grid;
  gap: 10px;
}

.meta-card {
  background: var(--surface-strong);
  border: 1px solid rgba(20, 46, 72, 0.12);
  border-radius: var(--radius-lg);
  min-width: 150px;
  padding: 10px 12px;
}

.meta-label {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.meta-value {
  font-family: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  font-size: 28px;
  font-weight: 700;
}

.panel-card {
  animation: rise-fade 450ms ease both;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
}

.panel-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.section-title {
  font-size: 27px;
  margin: 0;
}

.cards-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

.group-card,
.topic-card {
  background: var(--surface-strong);
  border: 1px solid rgba(16, 39, 64, 0.12);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.group-card-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.group-name {
  font-size: 17px;
  margin: 0;
}

.small-link {
  color: var(--brand-blue-strong);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
}

.small-link:hover {
  text-decoration: underline;
}

.group-description {
  color: var(--ink-soft);
  margin: 0;
}

.group-actions {
  display: flex;
  gap: 8px;
}

.assign-row {
  align-items: center;
  border-top: 1px solid rgba(20, 45, 72, 0.12);
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr 1fr;
  padding-top: 12px;
}

.assign-title {
  font-size: 18px;
  margin: 0 0 4px;
}

.assign-hint {
  color: var(--ink-soft);
  font-size: 13px;
  margin: 0;
}

.assign-controls {
  align-items: center;
  display: flex;
  gap: 8px;
}

.create-topic-box {
  border: 1px dashed rgba(20, 45, 72, 0.24);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.create-title {
  font-size: 18px;
  margin: 0;
}

.empty-box {
  border: 1px dashed rgba(20, 45, 72, 0.24);
  border-radius: var(--radius-md);
  color: var(--ink-soft);
  padding: 14px;
}

@media (max-width: 960px) {
  .subject-hero {
    grid-template-columns: 1fr;
  }

  .assign-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .assign-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .group-actions {
    flex-direction: column;
  }
}
</style>
