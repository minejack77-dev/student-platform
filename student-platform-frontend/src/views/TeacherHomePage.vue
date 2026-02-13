<script setup>
import { ref, onMounted, watch } from "vue";
import { Group, Topic } from "@/api.js";

const groupList = ref([]);
const topicList = ref([]);

const groupFilters = ref({ title: "" });
const topicFilters = ref({ title: "" });

const getGroups = async () => {
  const response = await Group.filter(groupFilters.value);
  groupList.value = response.results ?? response;
};

const getTopics = async () => {
  const response = await Topic.filter(topicFilters.value);
  topicList.value = response.results ?? response;
};

watch(
  () => groupFilters.value,
  () => getGroups(),
  { deep: true },
);

watch(
  () => topicFilters.value,
  () => getTopics(),
  { deep: true },
);

onMounted(() => {
  getGroups();
  getTopics();
});
</script>

<template>
  <div class="container teacher-page">
    <h1 class="visually-hidden">Страница преподавателя</h1>

    <section class="teacher-section">
      <div class="section-title">Мои группы</div>
      <div class="row row-cols-2 row-cols-md-4 g-4 section-grid">
        <div class="col" v-for="group in groupList" :key="group.id">
          <div class="card section-card">
            <div class="card-body">
              <h5 class="card-title">{{ group.name }}</h5>
              <p class="card-text">{{ group.description }}</p>
              <router-link
                :to="{ name: 'group-detail', params: { id: group.id } }"
                class="card-link"
              >
                Открыть
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="teacher-section">
      <div class="section-title">Мои топики</div>
      <div class="row row-cols-2 row-cols-md-4 g-4 section-grid">
        <div class="col" v-for="topic in topicList" :key="topic.id">
          <div class="card section-card">
            <div class="card-body">
              <h5 class="card-title">{{ topic.title }}</h5>
              <p class="card-text">{{ topic.description }}</p>
              <router-link
                :to="{ name: 'topic-detail', params: { id: topic.id } }"
                class="card-link"
              >
                Открыть
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.teacher-page {
  display: flex;
  flex-direction: column;
  gap: 32px;
  margin-bottom: 48px;
  max-width: 1100px;
}

.teacher-section {
  background: #2f5fe8;
  border-radius: 10px;
  padding: 28px 20px 24px;
}

.section-title {
  background: #d9d9d9;
  border-radius: 4px;
  color: #1f1f1f;
  font-size: 22px;
  font-weight: 500;
  margin: -12px 8px 22px;
  padding: 10px 0;
  text-align: center;
}

.section-grid {
  margin: 0;
}

.section-card {
  background: #d9d9d9;
  border: none;
  border-radius: 6px;
  min-height: 140px;
}

.section-card .card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
}

.section-card .card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.section-card .card-text {
  color: #2d2d2d;
  font-size: 13px;
  flex: 1;
  margin-bottom: 0;
}

.section-card .card-link {
  color: #1f1f1f;
  font-size: 12px;
  text-decoration: underline;
}

@media (max-width: 576px) {
  .teacher-page {
    gap: 24px;
  }

  .section-title {
    font-size: 18px;
  }
}
</style>
