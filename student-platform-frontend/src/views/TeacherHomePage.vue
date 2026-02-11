<script setup>
import { ref, onMounted, watch } from "vue";
import { Group } from "@/api.js";
let groupList = ref([]);

let filters = ref({ title: "" });

watch(
  () => filters.value,
  () => getGroup(),
  { deep: true },
);
let getGroup = async () => {
  let request = await Group.filter(filters.value);
  groupList.value = request.results;
};
onMounted(async () => {
  getGroup();
});
</script>

<template>
  <h1>Страница преподавателя</h1>
  <div class="container">
    <div class="row">
      <div class="col-sm-12">
        <h2>мои группы</h2>
        <div class="row row-cols-1 row-cols-md-4 g-4">
          <div class="col" v-for="group in groupList">
            <div class="card">
              <div class="card-body">
                <h5 class="card-title">{{ group.name }}</h5>
                <p class="card-text">
                  {{ group.description }}
                </p>
                <router-link
                  :to="{ name: 'group-detail', params: { id: group.id } }"
                  class="card-link"
                  >Card link</router-link
                >
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
