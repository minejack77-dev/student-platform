<script setup>
import { computed, ref, onMounted, watch } from "vue";
import { Group } from "@/api.js";

const props = defineProps(["id"]);
const group = ref({ students: [] });

const loadGroup = async () => {
  const response = await Group.get(props.id);
  group.value = {
    ...response,
    students: response.students ?? [],
  };
};

watch(
  () => props.id,
  () => loadGroup(),
);

onMounted(() => {
  loadGroup();
});

const studentCount = computed(() => group.value.students.length);
</script>

<template>
  <div class="container group-page">
    <h1 class="visually-hidden">Страница группы</h1>

    <section class="group-panel">
      <div class="group-header">Группа: {{ group.name }}</div>

      <div class="row g-3 group-meta">
        <div class="col-md-7">
          <div class="group-box">Всего студентов: {{ studentCount }}</div>
        </div>
        <div class="col-md-5">
          <router-link class="group-box group-box--link" to="/">
            На главную
          </router-link>
        </div>
      </div>

      <div class="group-students">
        <div
          class="group-box"
          v-for="(student, index) in group.students"
          :key="student.id"
        >
          Студент {{ index + 1 }}: {{ student.username || student.user }}
        </div>
        <div v-if="group.students.length === 0" class="group-box">
          Студентов пока нет
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.group-page {
  margin-bottom: 48px;
  max-width: 1100px;
}

.group-panel {
  background: #2f5fe8;
  border-radius: 10px;
  padding: 18px 18px 24px;
}

.group-header {
  background: #d9d9d9;
  border-radius: 6px;
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 18px;
  padding: 10px 16px;
}

.group-meta {
  margin-bottom: 18px;
}

.group-box {
  background: #d9d9d9;
  border-radius: 6px;
  color: #1f1f1f;
  display: block;
  font-size: 14px;
  padding: 12px 16px;
  text-decoration: none;
}

.group-box--link {
  align-items: center;
  display: flex;
  justify-content: center;
  text-align: center;
  height: 100%;
}

.group-students {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 576px) {
  .group-panel {
    padding: 14px;
  }

  .group-header {
    font-size: 16px;
  }
}
</style>
