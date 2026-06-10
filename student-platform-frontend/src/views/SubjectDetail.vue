<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Group, Subject, Topic, Unit, Workbook } from "@/api.js";

const props = defineProps(["id"]);

const subject = ref({});
const groups = ref([]);
const topics = ref([]);
const workbooks = ref([]);
const units = ref([]);
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
  workbook: "",
  unit: "",
  new_workbook_title: "",
  new_unit_title: "",
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

const selectedWorkbookId = computed(() => Number(createTopicForm.value.workbook) || null);

const workbookUnits = computed(() => {
  if (!selectedWorkbookId.value) {
    return [];
  }
  return units.value.filter((unit) => unit.workbook === selectedWorkbookId.value);
});

const loadSubject = async () => {
  const response = await Subject.get(props.id);
  subject.value = response;
};

const loadTopics = async () => {
  const response = await Topic.filter({
    subject: props.id,
  });
  topics.value = response.results ?? response;
};

const loadWorkbooks = async () => {
  const response = await Workbook.filter({
    subject: props.id,
    is_active: true,
    ordering: "title",
  });
  workbooks.value = response.results ?? response;
};

const loadUnits = async () => {
  const response = await Unit.filter({
    subject: props.id,
    is_active: true,
    ordering: "title",
  });
  units.value = response.results ?? response;
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
    await Promise.all([loadSubject(), loadTopics(), loadGroups(), loadWorkbooks(), loadUnits()]);
  } catch {
    loadError.value = "Failed to load subject page.";
  }
};

const resetCreateTopicForm = () => {
  createTopicForm.value = {
    title: "",
    description: "",
    is_active: true,
    workbook: "",
    unit: "",
    new_workbook_title: "",
    new_unit_title: "",
  };
  createTopicError.value = "";
};

const getTopicPlacementLabel = (topic) =>
  [topic.workbook_title, topic.unit_title, topic.title].filter(Boolean).join(" / ");

const getCreateTopicErrorMessage = (error) => {
  const payload = error?.response?.data;
  return (
    payload?.unit?.[0] ||
    payload?.workbook?.[0] ||
    payload?.title?.[0] ||
    payload?.detail ||
    "Could not create topic."
  );
};

const ensureWorkbookForTopic = async () => {
  if (createTopicForm.value.workbook) {
    return Number(createTopicForm.value.workbook);
  }

  const workbook = await Workbook.save({
    subject: numericSubjectId.value,
    title: createTopicForm.value.new_workbook_title.trim(),
    description: "",
    is_active: true,
  });
  return workbook.id;
};

const ensureUnitForTopic = async (workbookId) => {
  if (createTopicForm.value.unit) {
    return Number(createTopicForm.value.unit);
  }

  const unit = await Unit.save({
    workbook: workbookId,
    title: createTopicForm.value.new_unit_title.trim(),
    description: "",
    is_active: true,
  });
  return unit.id;
};

const createTopic = async () => {
  createTopicError.value = "";
  if (!createTopicForm.value.title.trim()) {
    createTopicError.value = "Topic title is required.";
    return;
  }
  if (!createTopicForm.value.workbook && !createTopicForm.value.new_workbook_title.trim()) {
    createTopicError.value = "Choose a workbook or enter a new workbook title.";
    return;
  }
  if (!createTopicForm.value.unit && !createTopicForm.value.new_unit_title.trim()) {
    createTopicError.value = "Choose a unit or enter a new unit title.";
    return;
  }

  createTopicLoading.value = true;
  try {
    const workbookId = await ensureWorkbookForTopic();
    const unitId = await ensureUnitForTopic(workbookId);
    await Topic.save({
      subject: numericSubjectId.value,
      unit: unitId,
      title: createTopicForm.value.title.trim(),
      description: createTopicForm.value.description.trim(),
      is_active: createTopicForm.value.is_active,
    });
    resetCreateTopicForm();
    await Promise.all([loadTopics(), loadWorkbooks(), loadUnits()]);
  } catch (error) {
    createTopicError.value = getCreateTopicErrorMessage(error);
  } finally {
    createTopicLoading.value = false;
  }
};

watch(
  () => createTopicForm.value.workbook,
  (nextValue, previousValue) => {
    if (nextValue === previousValue) {
      return;
    }
    createTopicForm.value.unit = "";
    if (nextValue) {
      createTopicForm.value.new_workbook_title = "";
    }
  },
);

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
              :to="{ name: 'group-details', params: { id: group.id } }"
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
              {{ getTopicPlacementLabel(topic) }}
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
        <div class="topic-structure-grid">
          <div class="topic-structure-field">
            <label class="form-label mb-1">Workbook</label>
            <select
              v-model="createTopicForm.workbook"
              class="form-select form-select-sm"
            >
              <option value="">Create new workbook</option>
              <option
                v-for="workbook in workbooks"
                :key="workbook.id"
                :value="String(workbook.id)"
              >
                {{ workbook.title }}
              </option>
            </select>
          </div>
          <div
            v-if="!createTopicForm.workbook"
            class="topic-structure-field"
          >
            <label class="form-label mb-1">New workbook title</label>
            <input
              v-model="createTopicForm.new_workbook_title"
              class="form-control form-control-sm"
              type="text"
              placeholder="Workbook title"
            />
          </div>
          <div class="topic-structure-field">
            <label class="form-label mb-1">Unit</label>
            <select
              v-model="createTopicForm.unit"
              class="form-select form-select-sm"
              :disabled="!createTopicForm.workbook"
            >
              <option value="">
                {{ createTopicForm.workbook ? "Create new unit" : "Create a workbook first" }}
              </option>
              <option
                v-for="unit in workbookUnits"
                :key="unit.id"
                :value="String(unit.id)"
              >
                {{ unit.title }}
              </option>
            </select>
          </div>
          <div
            v-if="!createTopicForm.unit"
            class="topic-structure-field"
          >
            <label class="form-label mb-1">New unit title</label>
            <input
              v-model="createTopicForm.new_unit_title"
              class="form-control form-control-sm"
              type="text"
              placeholder="Unit title"
            />
          </div>
        </div>
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
          <div class="topic-path">{{ topic.workbook_title }} / {{ topic.unit_title }}</div>
          <p class="group-description">{{ topic.description || "No description" }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped src="./SubjectDetail.css"></style>

