import assert from "node:assert/strict";
import test from "node:test";
import { loadAssignmentOptions } from "../src/utils/assignmentOptions.js";

test("loads every page and sorts titles alphabetically with natural numbers", async () => {
  const calls = [];
  const api = { filter: async (filters) => {
    calls.push(filters);
    return filters.page === 1
      ? { results: [{ id: 10, title: "Задание 10" }, { id: 2, title: "Задание 2" }], links: { next: "?page=2" } }
      : { results: [{ id: 1, title: "Задание 1" }, { id: 3, title: "Азбука" }], links: { next: null } };
  } };
  const items = await loadAssignmentOptions(api, { topic: "5", is_active: true });
  assert.deepEqual(items.map(item => item.id), [3, 1, 2, 10]);
  assert.deepEqual(calls.map(call => call.page), [1, 2]);
  assert.ok(calls.every(call => call.topic === "5" && call.is_active && call.ordering === "title,id"));
});

test("reload includes a formerly empty test with its current question count", async () => {
  let count = 0;
  const api = { filter: async () => ({ results: [
    { id: 1, title: "Тест", active_question_count: count, questions_per_attempt: 10 },
  ], links: { next: null } }) };
  const initial = await loadAssignmentOptions(api, {});
  assert.equal(initial[0].active_question_count, 0);
  count = 15;
  const refreshed = await loadAssignmentOptions(api, {});
  assert.equal(refreshed[0].active_question_count, 15);
  assert.ok(refreshed[0].active_question_count >= refreshed[0].questions_per_attempt);
});

test("supports unpaginated responses and propagates errors on later pages", async () => {
  assert.deepEqual(await loadAssignmentOptions({ filter: async () => [] }, {}), []);
  await assert.rejects(loadAssignmentOptions({ filter: async ({ page }) => {
    if (page === 2) throw new Error("Network unavailable");
    return { results: [], links: { next: "?page=2" } };
  } }, {}), /Network unavailable/);
});
