<script setup>
import { apiError } from "@/utils/apiError";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { Group, Subject, Topic, Unit, Workbook } from "@/api.js";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import { useUnsavedChanges } from '@/composables/useUnsavedChanges';

const props = defineProps(["id"]);
const route = useRoute();
const { t } = useI18n();

const subject = ref({});
const groups = ref([]);
const topics = ref([]);
const workbooks = ref([]);
const units = ref([]);
const loadError = ref("");
const loading = ref(true);
const topicSearch = ref("");
const pendingClear = ref(null);
const filteredTopics = computed(() => topics.value.filter(topic =>
  [topic.title, topic.workbook_title, topic.unit_title].join(' ').toLocaleLowerCase().includes(topicSearch.value.trim().toLocaleLowerCase()),
));
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
const { pendingLeave, finishLeave } = useUnsavedChanges(() =>
  ['title', 'description', 'new_workbook_title', 'new_unit_title'].some(key => createTopicForm.value[key].trim()),
);

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
  loading.value = true;
  loadError.value = "";
  assignError.value = "";
  assignSuccess.value = "";
  try {
    await Promise.all([loadSubject(), loadTopics(), loadGroups(), loadWorkbooks(), loadUnits()]);
  } catch {
    loadError.value = t("subjectDetail.groupPageLoadError");
  } finally {
    loading.value = false;
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
  return apiError(error, "subjectDetail.errors.createLesson");
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
    createTopicError.value = t("subjectDetail.errors.lessonTitleRequired");
    return;
  }
  if (!createTopicForm.value.workbook && !createTopicForm.value.new_workbook_title.trim()) {
    createTopicError.value = t("subjectDetail.errors.chooseTextbook");
    return;
  }
  if (!createTopicForm.value.unit && !createTopicForm.value.new_unit_title.trim()) {
    createTopicError.value = t("subjectDetail.errors.chooseUnit");
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
    assignSuccess.value = t("subjectDetail.messages.subjectAssigned");
    await loadGroups();
  } catch (error) {
    assignError.value = apiError(error, "subjectDetail.errors.assignSubject");
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
    assignSuccess.value = t("subjectDetail.messages.assignmentUpdated");
    await loadGroups();
  } catch (error) {
    assignError.value = apiError(error, "subjectDetail.errors.updateLesson");
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
    assignSuccess.value = t("subjectDetail.messages.subjectRemoved");
    await loadGroups();
  } catch (error) {
    assignError.value = apiError(error, "subjectDetail.errors.removeSubject");
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
    <nav class="page-breadcrumbs" :aria-label="t('workstation.group.breadcrumbs')">
      <router-link :to="{name:'teacher-home', query:{view:'materials'}}">{{ t('workstation.nav.materials') }}</router-link>
      <router-link v-if="route.query.group" :to="{name: 'group-overview', params:{id:route.query.group}}">{{ t("ux.schedule") }}</router-link>
      <span aria-current="page">{{ subject.name }}</span>
    </nav>
    <header class="subject-heading">
      <div>
        <h1 class="subject-title">{{ subject.name || t("common.untitledSubject") }}</h1>
        <p class="subject-description">{{ subject.description || t("common.noDescriptionYet") }}</p>
      </div>

      <div class="hero-meta">
        <div class="meta-card">
          <div class="meta-label">{{ t("common.lessons") }}</div>
          <div class="meta-value">{{ loading || loadError ? '—' : topics.length }}</div>
        </div>
        <div class="meta-card">
          <div class="meta-label">{{ t("subjectDetail.groupsAssigned") }}</div>
          <div class="meta-value">{{ loading || loadError ? '—' : assignedGroups.length }}</div>
        </div>
      </div>
    </header>

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError }} <button class="btn btn-link" @click="loadSubjectPage">{{ t('ux.retry') }}</button></div>
    <p v-if="loading" role="status">{{ t('common.loading') }}</p>
    <div v-if="assignError" class="alert alert-danger" role="alert">{{ assignError }}</div>
    <div v-if="assignSuccess" class="alert alert-success" role="status">{{ assignSuccess }}</div>



    <section v-if="!loading && !loadError" class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t("subjectDetail.lessonsInSubject") }}</h2>
        <span class="pill">{{ t("common.totalCount", { count: topics.length }) }}</span>
      </div>

      <label class="field-wrap">{{ t('workstation.materials.search') }}<input v-model="topicSearch" type="search" class="form-control" /></label>
      <details class="create-topic-box">
        <summary>{{ t("subjectDetail.createLesson") }}</summary>
        <div class="topic-structure-grid">
          <div class="topic-structure-field">
            <label class="form-label mb-1" for="topic-workbook">{{ t("common.textbook") }}</label>
            <select
              id="topic-workbook" v-model="createTopicForm.workbook"
              class="form-select form-select-sm"
            >
              <option value="">{{ t("subjectDetail.createNewTextbook") }}</option>
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
            <label class="form-label mb-1" for="topic-new_workbook_title">{{ t("subjectDetail.newTextbookTitle") }}</label>
            <input
              id="topic-new_workbook_title" v-model="createTopicForm.new_workbook_title"
              class="form-control form-control-sm"
              type="text"
              :placeholder="t('subjectDetail.textbookTitlePlaceholder')"
            />
          </div>
          <div class="topic-structure-field">
            <label class="form-label mb-1" for="topic-unit">{{ t("common.unit") }}</label>
            <select
              id="topic-unit" v-model="createTopicForm.unit"
              class="form-select form-select-sm"
              :disabled="!createTopicForm.workbook"
            >
              <option value="">
                {{ createTopicForm.workbook ? t("subjectDetail.createNewUnit") : t("subjectDetail.createTextbookFirst") }}
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
            <label class="form-label mb-1" for="topic-new_unit_title">{{ t("subjectDetail.newUnitTitle") }}</label>
            <input
              id="topic-new_unit_title" v-model="createTopicForm.new_unit_title"
              class="form-control form-control-sm"
              type="text"
              :placeholder="t('subjectDetail.unitTitlePlaceholder')"
            />
          </div>
        </div>
        <label class="form-label" for="topic-title">{{ t("common.title") }}</label>
        <input
          id="topic-title" :aria-describedby="createTopicError ? 'create-topic-error' : undefined" v-model="createTopicForm.title"
          class="form-control form-control-sm"
          type="text"
          :placeholder="t('subjectDetail.lessonTitlePlaceholder')"
        />
        <label class="form-label" for="topic-description">{{ t("common.description") }}</label>
        <textarea
          id="topic-description" :aria-describedby="createTopicError ? 'create-topic-error' : undefined" v-model="createTopicForm.description"
          class="form-control form-control-sm"
          rows="2"
          :placeholder="t('common.description')"
        />
        <div class="form-check">
          <input id="topic-active" v-model="createTopicForm.is_active" class="form-check-input" type="checkbox" />
          <label class="form-check-label" for="topic-active">{{ t("common.active") }}</label>
        </div>
        <div v-if="createTopicError" id="create-topic-error" class="small text-danger" role="alert">{{ createTopicError }}</div>
        <button class="btn btn-primary btn-sm" type="button" :disabled="createTopicLoading" @click="createTopic">
          {{ createTopicLoading ? t("common.creating") : t("subjectDetail.createLesson") }}
        </button>
      </details>

      <div v-if="topics.length === 0" class="empty-box">{{ t("subjectDetail.noLessonsYet") }}</div>

      <div v-if="topics.length && !filteredTopics.length" class="empty-box">{{ t('ux.noMatches') }} <button class="btn btn-link" @click="topicSearch = ''">{{ t('ux.clearSearch') }}</button></div>
      <div class="cards-grid topic-list">
        <article
          v-for="topic in filteredTopics"
          :key="topic.id"
          class="topic-card"
        >
          <div class="group-card-head">
            <h3 class="group-name">{{ topic.title }}</h3>
            <router-link
              class="small-link"
              :to="{ name: 'topic-detail', params: { id: topic.id }, query: { group: route.query.group } }"
            >
              {{ t("common.openLesson") }}
            </router-link>
          </div>
          <div class="topic-path">{{ topic.workbook_title }} / {{ topic.unit_title }}</div>
          <p class="group-description">{{ topic.description || t("common.noDescription") }}</p>
        </article>
      </div>
    </section>
    <section v-if="!loading && !loadError" class="surface-card panel-card">
      <div class="panel-head">
        <h2 class="section-title">{{ t("subjectDetail.groupsInSubject") }}</h2>
        <span class="pill">{{ t("common.groupsCount", { count: assignedGroups.length }) }}</span>
      </div>

      <div v-if="assignedGroups.length === 0" class="empty-box">
        {{ t("subjectDetail.noAssignedGroups") }}
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
              {{ t("common.openGroup") }}
            </router-link>
          </div>

          <p class="group-description">{{ group.description || t("common.noDescription") }}</p>

          <label class="form-label mb-1" :for="`group-topic-${group.id}`">{{ t("subjectDetail.lessonForGroup") }}</label>
          <select
            :id="`group-topic-${group.id}`" v-model="selectedTopicByGroup[group.id]"
            class="form-select form-select-sm"
          >
            <option value="">{{ t("subjectDetail.noLessonSelected") }}</option>
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
              {{ assignLoadingByGroup[group.id] ? t("common.saving") : t("subjectDetail.saveLesson") }}
            </button>
            <button
              class="btn btn-outline-danger btn-sm"
              type="button"
              :disabled="assignLoadingByGroup[group.id]"
              @click="pendingClear = group"
            >
              {{ t("subjectDetail.removeSubject") }}
            </button>
          </div>
        </article>
      </div>

      <div class="assign-row">
        <div class="assign-copy">
          <h3 class="assign-title">{{ t("subjectDetail.assignTitle") }}</h3>
          <p class="assign-hint">
            {{ t("subjectDetail.assignHint") }}
          </p>
        </div>
        <div class="assign-controls">
          <select v-model="selectedGroupToAssign" class="form-select" :aria-label="t('subjectDetail.chooseGroup')">
            <option value="">{{ t("subjectDetail.chooseGroup") }}</option>
            <option v-for="group in availableGroups" :key="group.id" :value="group.id">
              {{ group.name }}
            </option>
          </select>
          <button class="btn btn-outline-primary" type="button" :disabled="!selectedGroupToAssign || assignLoadingByGroup[selectedGroupToAssign]" @click="assignSelectedGroup">
            {{ t("subjectDetail.assignSubject") }}
          </button>
        </div>
      </div>
    </section>
    <ConfirmDialog v-if="pendingClear" :title="t('subjectDetail.removeSubject')" :description="t('workstation.materials.removeSubject', {name: pendingClear.name})" :confirm-label="t('common.remove')" @cancel="pendingClear = null" @confirm="clearSubjectFromGroup(pendingClear.id); pendingClear = null" />
    <ConfirmDialog v-if="pendingLeave" :title="t('workstation.materials.leaveTitle')" :description="t('workstation.materials.leaveHint')" :confirm-label="t('workstation.materials.leave')" @cancel="finishLeave(false)" @confirm="finishLeave(true)" />
  </div>
</template>

<style scoped src="./SubjectDetail.css"></style>

