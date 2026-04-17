<script setup>
import axios from "axios";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Group, Subject, Topic } from "@/api.js";

const props = defineProps(["id"]);

const group = ref({ students: [] });
const loadError = ref("");

const subjects = ref([]);
const topics = ref([]);
const assignmentForm = ref({
  subject: "",
  topic: "",
});
const assignmentLoading = ref(false);
const assignmentError = ref("");
const assignmentSuccess = ref("");

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

const loadSubjects = async () => {
  const response = await Subject.filter({ is_active: true, ordering: "name" });
  subjects.value = response.results ?? response;
};

const loadTopicsBySubject = async (subjectId) => {
  if (!subjectId) {
    topics.value = [];
    return;
  }
  const response = await Topic.filter({
    subject: subjectId,
    is_active: true,
    ordering: "title",
  });
  topics.value = response.results ?? response;
};

const loadTeacherAssignment = async () => {
  assignmentError.value = "";
  const assignment = await Group.getTeacherAssignment(props.id);
  assignmentForm.value.subject = assignment.subject ?? "";
  assignmentForm.value.topic = assignment.topic ?? "";
  await loadTopicsBySubject(assignmentForm.value.subject);
};

const saveTeacherAssignment = async () => {
  assignmentError.value = "";
  assignmentSuccess.value = "";
  assignmentLoading.value = true;
  try {
    const subjectId = assignmentForm.value.subject
      ? Number(assignmentForm.value.subject)
      : null;
    const topicId = assignmentForm.value.topic ? Number(assignmentForm.value.topic) : null;

    if (!subjectId) {
      await Group.clearTeacherAssignment(props.id);
      assignmentForm.value.subject = "";
      assignmentForm.value.topic = "";
      topics.value = [];
      assignmentSuccess.value = "Assignment cleared for your profile.";
    } else {
      await Group.saveTeacherAssignment(props.id, {
        subject: subjectId,
        topic: topicId,
      });
      assignmentSuccess.value = "Assignment saved for your profile.";
      await loadTopicsBySubject(subjectId);
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
  assignmentLoading.value = true;
  try {
    await Group.clearTeacherAssignment(props.id);
    assignmentForm.value.subject = "";
    assignmentForm.value.topic = "";
    topics.value = [];
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
  await loadTopicsBySubject(assignmentForm.value.subject);
};

const studentCount = computed(() => group.value.students.length);

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
    topics.value = [];
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
    await Promise.all([loadGroup(), loadSubjects()]);
    await loadTeacherAssignment();
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
  await Promise.all([loadGroup(), loadSubjects()]);
  await loadTeacherAssignment();
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
        This subject and topic are saved only for you. Other teachers can set their own assignments independently.
      </p>

      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label">Subject</label>
          <select v-model="assignmentForm.subject" class="form-select" @change="onSubjectChange">
            <option value="">No subject selected</option>
            <option v-for="subject in subjects" :key="subject.id" :value="subject.id">
              {{ subject.name }}
            </option>
          </select>
        </div>
        <div class="col-md-6">
          <label class="form-label">Topic</label>
          <select v-model="assignmentForm.topic" class="form-select" :disabled="!assignmentForm.subject">
            <option value="">No topic selected</option>
            <option v-for="topic in topics" :key="topic.id" :value="topic.id">
              {{ topic.title }}
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
            <div>
              <div class="member-name">{{ student.username || "Unknown" }}</div>
              <div class="member-meta">user id: {{ student.user }}</div>
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

