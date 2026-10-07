<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { getWorkspaceSection } from "@/composables/useWorkspaceNavigation";

import { Group, Subject } from "@/api.js";
import { apiError } from "@/utils/apiError";
import { useLocaleFormatting } from "@/composables/useLocaleFormatting";

import MaterialsLibrary from '@/components/MaterialsLibrary.vue';
const { t } = useI18n();
const organize = ref(false);
const route = useRoute();
watch(() => route.query.organize, value => { organize.value = value === '1'; }, { immediate: true });
const section = computed(() => getWorkspaceSection('teacher', route.query.view));
const { localeTag } = useLocaleFormatting();
const groupList = ref([]);
const subjectList = ref([]);
const groupFilters = ref({ name: "" });
const subjectFilters = ref({ name: "" });
const groupSort = ref("name");
const subjectSort = ref("name");
const loadError = ref("");
const groupLoading = ref(true);
const subjectLoading = ref(true);
const groupError = ref("");
const subjectError = ref("");
let groupRequest = 0;
let subjectRequest = 0;

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
  const request = ++groupRequest;
  groupLoading.value = true;
  groupError.value = "";
  try {
  const ordering = groupSort.value === "updated" ? "-updated_at" : "name";
  const response = await Group.filter({
    ...groupFilters.value,
    ordering,
  });
  if (request === groupRequest) groupList.value = response.results ?? response;
  } catch (error) {
    if (request === groupRequest) groupError.value = apiError(error);
  } finally {
    if (request === groupRequest) groupLoading.value = false;
  }
};

const getSubjects = async () => {
  const request = ++subjectRequest;
  subjectLoading.value = true;
  subjectError.value = "";
  try {
  const ordering = subjectSort.value === "updated" ? "-updated_at" : "name";
  const response = await Subject.filter({
    ...subjectFilters.value,
    ordering,
  });
  if (request === subjectRequest) subjectList.value = response.results ?? response;
  } catch (error) {
    if (request === subjectRequest) subjectError.value = apiError(error);
  } finally {
    if (request === subjectRequest) subjectLoading.value = false;
  }
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
    createGroupError.value = apiError(error, "teacherHome.errors.createGroup");
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
    createSubjectError.value = apiError(error, "teacherHome.errors.createSubject");
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
    <header class="workspace-heading">
      <div>
        <h1>{{ t(`workstation.nav.${section}`) }}</h1>
        <p>{{ t(`workstation.description.${section}`) }}</p>
      </div>
      <button v-if="section === 'groups'" class="btn btn-primary" type="button" @click="isCreatingGroup = true">+ {{ t('teacherHome.addGroup') }}</button>
      <button v-if="section === 'materials'" class="btn btn-outline-primary" type="button" :aria-expanded="organize" @click="organize = !organize">{{ t('materialsFlow.subjects') }}</button>
    </header>

    <div v-if="loadError" class="alert alert-danger">{{ loadError }}</div>

    <section v-show="section !== 'materials'" class="surface-card section-card">
      <div class="section-head">
      <div>
        <h2 class="section-title">{{ t("common.groups") }}</h2>
        <p v-if="!groupLoading && !groupError" class="section-subtitle">{{ t('workstation.found', { count: groupsCount }) }}</p>
      </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'name' }"
              :aria-pressed="groupSort === 'name'"
              type="button"
              :title="t('teacherHome.sortByName')"
              @click="setGroupSort('name')"
            >
              <span>{{ t("teacherHome.name") }}</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: groupSort === 'updated' }"
              :aria-pressed="groupSort === 'updated'"
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
              :aria-label="t('teacherHome.searchGroups')"
            />
          </div>
        </div>
      </div>

      <div v-if="groupLoading" role="status">{{ t('ux.loading') }}</div>
      <div v-else-if="groupError" class="alert alert-danger" role="alert">{{ groupError }} <button class="btn btn-outline-primary" @click="getGroups">{{ t('ux.retry') }}</button></div>
      <div v-else-if="groupList.length === 0" class="empty-box">{{ t("teacherHome.noGroups") }}</div>

      <div class="cards-grid">
        <article v-show="section === 'groups' && isCreatingGroup" class="entity-card add-card">
          <template v-if="isCreatingGroup">
            <div class="add-form">
              <label for="create-group-name">{{ t('teacherHome.groupName') }}</label>
              <input id="create-group-name"
                v-model="createGroupForm.name"
                class="form-control form-control-sm"
                type="text"
                :placeholder="t('teacherHome.groupName')"
                :aria-label="t('teacherHome.groupName')"
                :aria-describedby="createGroupError ? 'create-group-error' : undefined"
                :aria-invalid="!!createGroupError && !createGroupForm.name.trim()"
              />
              <label for="create-group-description">{{ t('common.description') }}</label>
              <textarea id="create-group-description"
                v-model="createGroupForm.description"
                class="form-control form-control-sm"
                rows="2"
                :placeholder="t('common.description')"
                :aria-label="t('common.description')"
              />
              <div class="form-check">
                <input id="new-group-active" v-model="createGroupForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-group-active">{{ t("common.active") }}</label>
              </div>
              <div v-if="createGroupError" id="create-group-error" class="small text-danger" role="alert">{{ createGroupError }}</div>
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
          v-for="group in (groupError || groupLoading ? [] : groupList)"
          :key="group.id"
          class="entity-card"
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
            <router-link :to="{ name: 'group-overview', params: { id: group.id }, query: section === 'results' ? { tab: 'results' } : {} }" class="entity-link entity-link-primary">
              {{ section === 'results' ? t('workstation.openResults') : t("teacherHome.overview") }}
            </router-link>
            <router-link :to="{ name: 'group-details', params: { id: group.id } }" class="entity-link entity-link-secondary">
              {{ t("teacherHome.details") }}
            </router-link>
          </div>
        </article>
      </div>
    </section>

    <MaterialsLibrary v-if="section === 'materials' && !organize" />
    <section v-show="section === 'materials' && organize" class="surface-card section-card">
      <button class="btn btn-primary mb-3" @click="isCreatingSubject = true">{{ t('teacherHome.addSubject') }}</button>
      <div class="section-head">
        <div>
          <h2 class="section-title">{{ t("common.subject") }}</h2>
          <p v-if="!subjectLoading && !subjectError" class="section-subtitle">{{ t('workstation.found', { count: subjectsCount }) }}</p>
        </div>
        <div class="controls-wrap">
          <div class="sort-switch">
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'name' }"
              :aria-pressed="subjectSort === 'name'"
              type="button"
              :title="t('teacherHome.sortByName')"
              @click="setSubjectSort('name')"
            >
              <span>{{ t("teacherHome.name") }}</span>
            </button>
            <button
              class="sort-btn"
              :class="{ active: subjectSort === 'updated' }"
              :aria-pressed="subjectSort === 'updated'"
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
              :aria-label="t('teacherHome.searchSubjects')"
            />
          </div>
        </div>
      </div>

      <div v-if="subjectLoading" role="status">{{ t('ux.loading') }}</div>
      <div v-else-if="subjectError" class="alert alert-danger" role="alert">{{ subjectError }} <button class="btn btn-outline-primary" @click="getSubjects">{{ t('ux.retry') }}</button></div>
      <div v-else-if="subjectList.length === 0" class="empty-box">{{ t("teacherHome.noSubjects") }}</div>

      <div class="cards-grid">
        <article v-show="isCreatingSubject" class="entity-card add-card">
          <template v-if="isCreatingSubject">
            <div class="add-form">
              <label for="create-subject-name">{{ t('teacherHome.subjectName') }}</label>
              <input id="create-subject-name"
                v-model="createSubjectForm.name"
                class="form-control form-control-sm"
                type="text"
                :placeholder="t('teacherHome.subjectName')"
                :aria-label="t('teacherHome.subjectName')"
                :aria-describedby="createSubjectError ? 'create-subject-error' : undefined"
                :aria-invalid="!!createSubjectError && !createSubjectForm.name.trim()"
              />
              <label for="create-subject-description">{{ t('common.description') }}</label>
              <textarea id="create-subject-description"
                v-model="createSubjectForm.description"
                class="form-control form-control-sm"
                rows="2"
                :placeholder="t('common.description')"
                :aria-label="t('common.description')"
              />
              <div class="form-check">
                <input id="new-subject-active" v-model="createSubjectForm.is_active" class="form-check-input" type="checkbox" />
                <label class="form-check-label" for="new-subject-active">{{ t("common.active") }}</label>
              </div>
              <div v-if="createSubjectError" id="create-subject-error" class="small text-danger" role="alert">{{ createSubjectError }}</div>
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
          v-for="subject in (subjectError || subjectLoading ? [] : subjectList)"
          :key="subject.id"
          class="entity-card"
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
