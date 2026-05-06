<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Group, Subject } from "@/api.js";

const groupList = ref([]);
const subjectList = ref([]);
const groupFilters = ref({ name: "" });
const subjectFilters = ref({ name: "" });
const groupSort = ref("name");
const subjectSort = ref("name");
const loadError = ref("");

const isCreatingGroup = ref(false);
const isCreatingSubject = ref(false);
const createGroupLoading = ref(false);
const createSubjectLoading = ref(false);
const createGroupError = ref("");
const createSubjectError = ref("");
const createGroupForm = ref({
  name: "",
  description: "",
  is_active: true,
});
const createSubjectForm = ref({
  name: "",
  description: "",
  is_active: true,
});

const getGroups = async () => {
  const ordering = groupSort.value === "updated" ? "-updated_at" : "name";
  const response = await Group.filter({
    ...groupFilters.value,
    ordering,
  });
  groupList.value = response.results ?? response;
};

const getSubjects = async () => {
  const ordering = subjectSort.value === "updated" ? "-updated_at" : "name";
  const response = await Subject.filter({
    ...subjectFilters.value,
    ordering,
  });
  subjectList.value = response.results ?? response;
};

const loadDashboard = async () => {
  loadError.value = "";
  try {
    await Promise.all([getGroups(), getSubjects()]);
  } catch {
    loadError.value = "Could not load dashboard data.";
  }
};

const resetGroupForm = () => {
  createGroupForm.value = { name: "", description: "", is_active: true };
  createGroupError.value = "";
};

const resetSubjectForm = () => {
  createSubjectForm.value = { name: "", description: "", is_active: true };
  createSubjectError.value = "";
};

const createGroup = async () => {
  createGroupError.value = "";
  if (!createGroupForm.value.name.trim()) {
    createGroupError.value = "Group name is required.";
    return;
  }

  createGroupLoading.value = true;
  try {
    await Group.save({
      name: createGroupForm.value.name.trim(),
      description: createGroupForm.value.description.trim(),
      is_active: createGroupForm.value.is_active,
    });
    isCreatingGroup.value = false;
    resetGroupForm();
    await getGroups();
  } catch (error) {
    createGroupError.value =
      error?.response?.data?.name?.[0] || "Could not create group.";
  } finally {
    createGroupLoading.value = false;
  }
};

const createSubject = async () => {
  createSubjectError.value = "";
  if (!createSubjectForm.value.name.trim()) {
    createSubjectError.value = "Subject name is required.";
    return;
  }

  createSubjectLoading.value = true;
  try {
    await Subject.save({
      name: createSubjectForm.value.name.trim(),
      description: createSubjectForm.value.description.trim(),
      is_active: createSubjectForm.value.is_active,
    });
    isCreatingSubject.value = false;
    resetSubjectForm();
    await getSubjects();
  } catch (error) {
    createSubjectError.value =
      error?.response?.data?.name?.[0] || "Could not create subject.";
  } finally {
    createSubjectLoading.value = false;
  }
};

const setGroupSort = async (mode) => {
  if (groupSort.value === mode) {
    return;
  }
  groupSort.value = mode;
  await getGroups();
};

const setSubjectSort = async (mode) => {
  if (subjectSort.value === mode) {
    return;
  }
  subjectSort.value = mode;
  await getSubjects();
};

const formatUpdatedAt = (value) => {
  if (!value) {
    return "No edits yet";
  }
  return new Date(value).toLocaleString();
};

watch(
  () => groupFilters.value,
  () => getGroups(),
  { deep: true },
);

watch(
  () => subjectFilters.value,
  () => getSubjects(),
  { deep: true },
);

onMounted(async () => {
  await loadDashboard();
});

const groupsCount = computed(() => groupList.value.length);
const subjectsCount = computed(() => subjectList.value.length);
</script>

<template>
  <div class="teacher-page">
    <section class="surface-card hero-panel">
      <div class="hero-copy">
        <span class="pill">Workspace</span>
        <h1 class="hero-title">Teaching Hub</h1>
        <p class="hero-subtitle">
          Manage groups and subjects. Subject/topic assignment is personal for each teacher.
        </p>
      </div>

      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-label">Groups</div>
          <div class="stat-value">{{ groupsCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Subjects</div>
          <div class="stat-value">{{ subjectsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section class="surface-card section-card">
      <div class="section-head">
      <div>
        <h2 class="section-title">Groups</h2>
        <p class="section-subtitle">Open a group to manage members, subject setup, and the date-based topic calendar.</p>
      </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'name' }"
              type="button"
              title="Sort by name"
              @click="setGroupSort('name')"
            >
              <span>Name</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'updated' }"
              type="button"
              title="Sort by last edited"
              @click="setGroupSort('updated')"
            >
              <span>Edited</span>
            </button>
          </div>
          <div class="search-wrap">
            <input
              v-model="groupFilters.name"
              class="form-control"
              type="text"
              placeholder="Search groups by name"
            />
          </div>
        </div>
      </div>

      <div v-if="groupList.length === 0" class="empty-box">No groups found.</div>

      <div class="cards-grid">
        <article class="entity-card add-card">
          <template v-if="!isCreatingGroup">
            <button class="add-entity-button" type="button" @click="isCreatingGroup = true">
              <span class="add-icon">+</span>
              <span>Add group</span>
            </button>
          </template>
          <template v-else>
            <div class="add-form">
              <input
                v-model="createGroupForm.name"
                class="form-control form-control-sm"
                type="text"
                placeholder="Group name"
              />
              <textarea
                v-model="createGroupForm.description"
                class="form-control form-control-sm"
                rows="2"
                placeholder="Description"
              />
              <div class="form-check">
                <input id="new-group-active" v-model="createGroupForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-group-active">Active</label>
              </div>
              <div v-if="createGroupError" class="small text-danger">{{ createGroupError }}</div>
              <div class="add-form-actions">
                <button class="btn btn-primary btn-sm" :disabled="createGroupLoading" type="button" @click="createGroup">
                  {{ createGroupLoading ? "Creating..." : "Create" }}
                </button>
                <button class="btn btn-outline-secondary btn-sm" type="button" @click="isCreatingGroup = false; resetGroupForm()">
                  Cancel
                </button>
              </div>
            </div>
          </template>
        </article>

        <article
          v-for="(group, index) in groupList"
          :key="group.id"
          class="entity-card"
          :style="{ '--delay': `${index * 50}ms` }"
        >
          <div class="entity-header">
            <h3 class="entity-title">{{ group.name }}</h3>
            <span class="entity-chip">Group</span>
          </div>
          <p class="entity-text">{{ group.description || "No description" }}</p>

          <div v-if="group.teacher_assignment" class="assignment-chip">
            {{ group.teacher_assignment.subject_name }}
          </div>
          <div v-else class="assignment-chip muted">No subject assigned for you yet.</div>

          <div class="entity-meta">Edited: {{ formatUpdatedAt(group.updated_at) }}</div>
          <router-link :to="{ name: 'group-detail', params: { id: group.id } }" class="entity-link">
            Open group
          </router-link>
        </article>
      </div>
    </section>

    <section class="surface-card section-card">
      <div class="section-head">
        <div>
          <h2 class="section-title">Subjects</h2>
          <p class="section-subtitle">Open a subject to view topics and assigned groups.</p>
        </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'name' }"
              type="button"
              title="Sort by name"
              @click="setSubjectSort('name')"
            >
              <span>Name</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'updated' }"
              type="button"
              title="Sort by last edited"
              @click="setSubjectSort('updated')"
            >
              <span>Edited</span>
            </button>
          </div>
          <div class="search-wrap">
            <input
              v-model="subjectFilters.name"
              class="form-control"
              type="text"
              placeholder="Search subjects by name"
            />
          </div>
        </div>
      </div>

      <div v-if="subjectList.length === 0" class="empty-box">No subjects found.</div>

      <div class="cards-grid">
        <article class="entity-card add-card">
          <template v-if="!isCreatingSubject">
            <button class="add-entity-button" type="button" @click="isCreatingSubject = true">
              <span class="add-icon">+</span>
              <span>Add subject</span>
            </button>
          </template>
          <template v-else>
            <div class="add-form">
              <input
                v-model="createSubjectForm.name"
                class="form-control form-control-sm"
                type="text"
                placeholder="Subject name"
              />
              <textarea
                v-model="createSubjectForm.description"
                class="form-control form-control-sm"
                rows="2"
                placeholder="Description"
              />
              <div class="form-check">
                <input id="new-subject-active" v-model="createSubjectForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-subject-active">Active</label>
              </div>
              <div v-if="createSubjectError" class="small text-danger">{{ createSubjectError }}</div>
              <div class="add-form-actions">
                <button class="btn btn-primary btn-sm" :disabled="createSubjectLoading" type="button" @click="createSubject">
                  {{ createSubjectLoading ? "Creating..." : "Create" }}
                </button>
                <button class="btn btn-outline-secondary btn-sm" type="button" @click="isCreatingSubject = false; resetSubjectForm()">
                  Cancel
                </button>
              </div>
            </div>
          </template>
        </article>

        <article
          v-for="(subject, index) in subjectList"
          :key="subject.id"
          class="entity-card"
          :style="{ '--delay': `${index * 50}ms` }"
        >
          <div class="entity-header">
            <h3 class="entity-title">{{ subject.name }}</h3>
            <span class="entity-chip">Subject</span>
          </div>
          <p class="entity-text">{{ subject.description || "No description" }}</p>
          <div class="entity-meta">Edited: {{ formatUpdatedAt(subject.updated_at) }}</div>
          <router-link :to="{ name: 'subject-detail', params: { id: subject.id } }" class="entity-link">
            Open subject
          </router-link>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped src="./TeacherHomePage.css"></style>
