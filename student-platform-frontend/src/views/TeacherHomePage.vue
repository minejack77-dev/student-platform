<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { Group, Subject } from "@/api.js";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

const { t } = useI18n();
const { localeTag } = useLocaleFormatting();
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
    loadError.value = t("teacherHome.loadError");
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
    createGroupError.value = t("teacherHome.errors.groupNameRequired");
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
      error?.response?.data?.name?.[0] || t("teacherHome.errors.createGroup");
  } finally {
    createGroupLoading.value = false;
  }
};

const createSubject = async () => {
  createSubjectError.value = "";
  if (!createSubjectForm.value.name.trim()) {
    createSubjectError.value = t("teacherHome.errors.subjectNameRequired");
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
      error?.response?.data?.name?.[0] || t("teacherHome.errors.createSubject");
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
    return t("teacherHome.noEditsYet");
  }
  return new Date(value).toLocaleString(localeTag.value);
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
        <span class="pill">{{ t("teacherHome.badge") }}</span>
        <h1 class="hero-title">{{ t("teacherHome.title") }}</h1>
        <p class="hero-subtitle">{{ t("teacherHome.subtitle") }}</p>
      </div>

      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-label">{{ t("common.groups") }}</div>
          <div class="stat-value">{{ groupsCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t("common.subjects") }}</div>
          <div class="stat-value">{{ subjectsCount }}</div>
        </div>
      </div>
    </section>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section class="surface-card section-card">
      <div class="section-head">
      <div>
        <h2 class="section-title">{{ t("common.groups") }}</h2>
        <p class="section-subtitle">{{ t("teacherHome.groupsSubtitle") }}</p>
      </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'name' }"
              type="button"
              :title="t('teacherHome.sortByName')"
              @click="setGroupSort('name')"
            >
              <span>{{ t("teacherHome.name") }}</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'updated' }"
              type="button"
              :title="t('teacherHome.sortByEdited')"
              @click="setGroupSort('updated')"
            >
              <span>{{ t("teacherHome.edited") }}</span>
            </button>
          </div>
          <div class="search-wrap">
            <input
              v-model="groupFilters.name"
              class="form-control"
              type="text"
              :placeholder="t('teacherHome.searchGroups')"
            />
          </div>
        </div>
      </div>

      <div v-if="groupList.length === 0" class="empty-box">{{ t("teacherHome.noGroups") }}</div>

      <div class="cards-grid">
        <article class="entity-card add-card">
          <template v-if="!isCreatingGroup">
            <button class="add-entity-button" type="button" @click="isCreatingGroup = true">
              <span class="add-icon">+</span>
              <span>{{ t("teacherHome.addGroup") }}</span>
            </button>
          </template>
          <template v-else>
            <div class="add-form">
              <input
                v-model="createGroupForm.name"
                class="form-control form-control-sm"
                type="text"
                :placeholder="t('teacherHome.groupName')"
              />
              <textarea
                v-model="createGroupForm.description"
                class="form-control form-control-sm"
                rows="2"
                :placeholder="t('common.description')"
              />
              <div class="form-check">
                <input id="new-group-active" v-model="createGroupForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-group-active">{{ t("common.active") }}</label>
              </div>
              <div v-if="createGroupError" class="small text-danger">{{ createGroupError }}</div>
              <div class="add-form-actions">
                <button class="btn btn-primary btn-sm" :disabled="createGroupLoading" type="button" @click="createGroup">
                  {{ createGroupLoading ? t("common.creating") : t("common.create") }}
                </button>
                <button class="btn btn-outline-secondary btn-sm" type="button" @click="isCreatingGroup = false; resetGroupForm()">
                  {{ t("common.cancel") }}
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
            <span class="entity-chip">{{ t("teacherHome.groupChip") }}</span>
          </div>
          <p class="entity-text">{{ group.description || t("common.noDescription") }}</p>

          <div v-if="group.teacher_assignment" class="assignment-chip">
            {{ group.teacher_assignment.subject_name }}
          </div>
          <div v-else class="assignment-chip muted">{{ t("teacherHome.noSubjectAssigned") }}</div>

          <div class="entity-meta">{{ t("teacherHome.edited") }}: {{ formatUpdatedAt(group.updated_at) }}</div>
          <div class="entity-link-row">
            <router-link :to="{ name: 'group-overview', params: { id: group.id } }" class="entity-link entity-link-primary">
              {{ t("teacherHome.overview") }}
            </router-link>
            <router-link :to="{ name: 'group-details', params: { id: group.id } }" class="entity-link entity-link-secondary">
              {{ t("teacherHome.details") }}
            </router-link>
          </div>
        </article>
      </div>
    </section>

    <section class="surface-card section-card">
      <div class="section-head">
        <div>
          <h2 class="section-title">{{ t("common.subject") }}</h2>
          <p class="section-subtitle">{{ t("teacherHome.subjectsSubtitle") }}</p>
        </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'name' }"
              type="button"
              :title="t('teacherHome.sortByName')"
              @click="setSubjectSort('name')"
            >
              <span>{{ t("teacherHome.name") }}</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'updated' }"
              type="button"
              :title="t('teacherHome.sortByEdited')"
              @click="setSubjectSort('updated')"
            >
              <span>{{ t("teacherHome.edited") }}</span>
            </button>
          </div>
          <div class="search-wrap">
            <input
              v-model="subjectFilters.name"
              class="form-control"
              type="text"
              :placeholder="t('teacherHome.searchSubjects')"
            />
          </div>
        </div>
      </div>

      <div v-if="subjectList.length === 0" class="empty-box">{{ t("teacherHome.noSubjects") }}</div>

      <div class="cards-grid">
        <article class="entity-card add-card">
          <template v-if="!isCreatingSubject">
            <button class="add-entity-button" type="button" @click="isCreatingSubject = true">
              <span class="add-icon">+</span>
              <span>{{ t("teacherHome.addSubject") }}</span>
            </button>
          </template>
          <template v-else>
            <div class="add-form">
              <input
                v-model="createSubjectForm.name"
                class="form-control form-control-sm"
                type="text"
                :placeholder="t('teacherHome.subjectName')"
              />
              <textarea
                v-model="createSubjectForm.description"
                class="form-control form-control-sm"
                rows="2"
                :placeholder="t('common.description')"
              />
              <div class="form-check">
                <input id="new-subject-active" v-model="createSubjectForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-subject-active">{{ t("common.active") }}</label>
              </div>
              <div v-if="createSubjectError" class="small text-danger">{{ createSubjectError }}</div>
              <div class="add-form-actions">
                <button class="btn btn-primary btn-sm" :disabled="createSubjectLoading" type="button" @click="createSubject">
                  {{ createSubjectLoading ? t("common.creating") : t("common.create") }}
                </button>
                <button class="btn btn-outline-secondary btn-sm" type="button" @click="isCreatingSubject = false; resetSubjectForm()">
                  {{ t("common.cancel") }}
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
            <span class="entity-chip">{{ t("teacherHome.subjectChip") }}</span>
          </div>
          <p class="entity-text">{{ subject.description || t("common.noDescription") }}</p>
          <div class="entity-meta">{{ t("teacherHome.edited") }}: {{ formatUpdatedAt(subject.updated_at) }}</div>
          <router-link :to="{ name: 'subject-detail', params: { id: subject.id } }" class="entity-link entity-link-primary">
            {{ t("teacherHome.openSubject") }}
          </router-link>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped src="./TeacherHomePage.css"></style>
