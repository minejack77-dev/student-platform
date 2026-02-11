<script setup>
import { ref, onMounted, watch } from "vue";
import { Group, Users } from "@/api.js";
const props = defineProps(["id"]);
let group = ref({});
let studentList = ref([]);

let filters = ref({ title: "" });

watch(
  () => filters.value,
  () => getGroup(),
  { deep: true },
);
let getGroup = async () => {
  let request = await Group.get(props.id);
  group.value = request;
  studentList.value = (await Users.filter()).results;
};
onMounted(async () => {
  getGroup();
});
</script>

<template>
  <h1>Страница группы {{ group.name }}</h1>
  <div class="container">
    <div class="row" v-for="student in studentList">
      <div class="col-sm-12">
        {{ student.username }}
      </div>
    </div>
  </div>
</template>
