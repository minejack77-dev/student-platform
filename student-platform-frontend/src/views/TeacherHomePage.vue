<script setup>
import { ref, onMounted, watch } from "vue";
import { Topic } from "@/api.js";
let topicList = ref([]);
let newTopic = ref({});

let filters = ref({ title: "" });

watch(
  () => filters.value,
  () => getTopic(),
  { deep: true },
);
let getTopic = async () => {
  let request = await Topic.filter(filters.value);
  topicList.value = request.results;
};
onMounted(async () => {
  getTopic();
});

let saveTopic = async () => {
  await Topic.save(newTopic.value);
  getTopic();
};
</script>

<template>
  <h1>Главаня страница</h1>
  поис по имени <input v-model="filters.title" />
  <div v-for="topic in topicList">
    <b>{{ topic.title }}</b>
    <div>{{ topic.description }}</div>
  </div>

  <hr />
  <input v-model="newTopic.title" />
  <input v-model="newTopic.description" />
  <button @click="saveTopic()">save</button>
</template>
