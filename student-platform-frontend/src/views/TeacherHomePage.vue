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
          <p class="section-subtitle">Open a group to manage members and your subject/topic setup.</p>
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
            <span v-if="group.teacher_assignment.topic_title">-> {{ group.teacher_assignment.topic_title }}</span>
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

<style scoped>
.teacher-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.hero-panel {
  align-items: end;
  animation: rise-fade 450ms ease both;
  background:
    radial-gradient(circle at 18% 12%, rgba(255, 179, 71, 0.2), transparent 44%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.84) 0%, rgba(242, 249, 255, 0.96) 100%);
  display: grid;
  gap: 20px;
  grid-template-columns: 1.2fr 0.8fr;
  padding: 26px;
}

.hero-title {
  font-size: clamp(30px, 4vw, 40px);
  margin: 10px 0 8px;
}

.hero-subtitle {
  color: var(--ink-soft);
  margin: 0;
  max-width: 560px;
}

.hero-stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
}

.stat-card {
  background: var(--surface-strong);
  border: 1px solid rgba(15, 42, 68, 0.1);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2);
  padding: 12px 14px;
}

.stat-label {
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.stat-value {
  font-family: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
}

.section-card {
  animation: rise-fade 500ms ease both;
  padding: 22px;
}

.section-head {
  align-items: flex-start;
  display: flex;
  gap: 18px;
  justify-content: space-between;
  margin-bottom: 16px;
  row-gap: 10px;
}

.controls-wrap {
  align-items: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  max-width: 100%;
}

.sort-switch {
  align-items: center;
  background: rgba(31, 95, 216, 0.08);
  border: 1px solid rgba(31, 95, 216, 0.18);
  border-radius: 12px;
  display: flex;
  gap: 4px;
  padding: 4px;
}

.sort-btn {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 9px;
  color: var(--ink-soft);
  display: inline-flex;
  font-size: 12px;
  font-weight: 700;
  gap: 6px;
  padding: 6px 8px;
  transition:
    background 120ms ease,
    color 120ms ease;
}

.sort-btn.active {
  background: rgba(31, 95, 216, 0.14);
  color: var(--brand-blue-strong);
}

.section-title {
  font-size: 28px;
  margin: 0;
}

.section-subtitle {
  color: var(--ink-soft);
  margin: 2px 0 0;
}

.search-wrap {
  min-width: 230px;
  width: clamp(230px, 28vw, 360px);
}

.empty-box {
  border: 1px dashed rgba(20, 45, 72, 0.22);
  border-radius: var(--radius-md);
  color: var(--ink-soft);
  margin-bottom: 12px;
  padding: 14px;
}

.cards-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
}

.entity-card {
  animation: rise-fade 400ms ease both;
  animation-delay: var(--delay);
  background: var(--surface-strong);
  border: 1px solid rgba(16, 39, 64, 0.12);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 190px;
  padding: 14px;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease;
}

.entity-card:hover {
  box-shadow: 0 12px 24px rgba(16, 38, 62, 0.14);
  transform: translateY(-2px);
}

.entity-header {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.entity-title {
  font-size: 18px;
  margin: 0;
}

.entity-chip {
  background: rgba(12, 169, 146, 0.14);
  border-radius: 999px;
  color: #097563;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  text-transform: uppercase;
}

.entity-text {
  color: var(--ink-soft);
  flex: 1;
  margin: 0;
}

.assignment-chip {
  background: rgba(31, 95, 216, 0.1);
  border-radius: 999px;
  color: var(--brand-blue-strong);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  width: fit-content;
}

.assignment-chip.muted {
  background: rgba(20, 40, 67, 0.08);
  color: var(--ink-soft);
}

.entity-meta {
  color: var(--ink-soft);
  font-size: 12px;
}

.entity-link {
  color: var(--brand-blue-strong);
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
}

.entity-link:hover {
  text-decoration: underline;
}

.add-card {
  align-items: stretch;
  border-style: dashed;
  border-width: 1px;
  justify-content: center;
}

.add-entity-button {
  align-items: center;
  background: transparent;
  border: none;
  color: var(--brand-blue-strong);
  display: flex;
  flex: 1;
  flex-direction: column;
  font-weight: 700;
  gap: 8px;
  justify-content: center;
}

.add-icon {
  align-items: center;
  border: 1px solid rgba(31, 95, 216, 0.34);
  border-radius: 14px;
  display: inline-flex;
  font-size: 30px;
  height: 54px;
  justify-content: center;
  line-height: 1;
  width: 54px;
}

.add-form {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
}

.add-form-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 900px) {
  .hero-panel {
    grid-template-columns: 1fr;
  }

  .hero-stats {
    grid-template-columns: repeat(2, minmax(130px, 1fr));
  }
}

@media (max-width: 1100px) {
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .controls-wrap {
    justify-content: flex-start;
  }
}

@media (max-width: 700px) {
  .controls-wrap {
    align-items: stretch;
    flex-direction: column;
  }

  .search-wrap {
    min-width: 0;
    width: 100%;
  }
}
</style>
