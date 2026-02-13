<script setup>
import { ref, onMounted, watch } from "vue";
import { Topic } from "@/api.js";

const props = defineProps(["id"]);
const topic = ref({});

const getTopic = async () => {
  const response = await Topic.get(props.id);
  topic.value = response;
};

watch(
  () => props.id,
  () => getTopic(),
);

onMounted(() => {
  getTopic();
});
</script>

<template>
  <div class="container topic-page">
    <h1 class="topic-title">Топик: {{ topic.title }}</h1>
    <div class="card topic-card">
      <div class="card-body">
        <div class="topic-row">
          <div class="topic-label">Описание</div>
          <div class="topic-value">
            {{ topic.description || "Без описания" }}
          </div>
        </div>
        <div class="topic-row">
          <div class="topic-label">Статус</div>
          <div class="topic-value">
            {{ topic.is_active ? "Активен" : "Не активен" }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.topic-page {
  max-width: 900px;
}

.topic-title {
  font-size: 24px;
  margin-bottom: 16px;
}

.topic-card {
  background: #f4f4f4;
  border: none;
  border-radius: 8px;
}

.topic-row {
  display: grid;
  gap: 8px;
  grid-template-columns: 140px 1fr;
  margin-bottom: 12px;
}

.topic-label {
  font-weight: 600;
}

.topic-value {
  color: #333;
}

@media (max-width: 576px) {
  .topic-row {
    grid-template-columns: 1fr;
  }
}
</style>
