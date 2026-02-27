<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Attempt, AttemptQuestion, Answer } from "@/api.js";

const props = defineProps(["id"]);
let attempt = ref({});
let questionList = ref({});
let questionCount = ref(0);

let activeQuestionIndex = ref(0);

let getAttempt = async () => {
  attempt.value = await Attempt.get(props.id);
  let response = await AttemptQuestion.filter({ attempt_id: props.id });
  for (let q of response.results) {
    if (q.answer) {
      for (let selected of q.answer.selected_choices) {
        for (let choice of q.question.choices) {
          if (choice.id == selected) {
            choice.isSelect = true;
          }
        }
      }
    }
  }
  questionList.value = response.results;
  questionCount.value = response.count;
};
onMounted(() => {
  getAttempt();
});

let activeQuestion = computed(() => {
  return questionList.value[activeQuestionIndex.value];
});
const nextQuestion = () => {
  activeQuestionIndex.value += 1;
};
const saveAnswer = () => {
  let selected_choices = [];
  for (let s of activeQuestion.value.question.choices) {
    if (s.isSelect) {
      selected_choices.push(s.id);
    }
  }
  let answer = {
    attempt_question: activeQuestion.value.question.id,
    selected_choices,
  };
  Answer.save(answer);
};
const complete = async () => {
  attempt.value.status = "completed";
  Attempt.save(attempt.value);
};
</script>
<template>
  <div>{{ attempt }} {{ questionCount }}</div>
  <div>{{ activeQuestion?.id }} {{ activeQuestion?.question?.text }}</div>
  <ul v-if="activeQuestion?.id">
    <li v-for="choice in activeQuestion.question.choices">
      <input v-model="choice.isSelect" type="checkbox" />{{ choice }}
    </li>
  </ul>
  <button @click="activeQuestionIndex -= 1">prev</button>
  <button @click="saveAnswer">save</button>

  <button @click="nextQuestion" v-if="activeQuestionIndex < questionCount">
    next
  </button>

  <button @click="complete" v-else="">complite</button>
</template>
