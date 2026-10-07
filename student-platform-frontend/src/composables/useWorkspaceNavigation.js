import { computed, toValue } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

const sections = {
  teacher: ["groups", "materials", "results"],
  student: ["assignments", "schedule", "results", "notifications"],
};

export function getWorkspaceSection(role, value) {
  const available = sections[role] || [];
  return available.includes(value) ? value : available[0];
}

export function useWorkspaceNavigation(role) {
  const route = useRoute();
  const { t } = useI18n();
  const items = computed(() => (sections[toValue(role)] || []).map((key) => ({
    key,
    label: t(`workstation.nav.${key}`),
    to: { name: `${toValue(role)}-home`, query: { view: key } },
  })));
  const activeKey = computed(() => {
    const currentRole = toValue(role);
    if (route.name === `${currentRole}-home`) {
      return getWorkspaceSection(currentRole, route.query.view);
    }
    if (currentRole === "teacher") {
      if (["subject-detail", "topic-detail", "task-create", "task-workspace"].includes(route.name)) return "materials";
      if (route.name === "attempt-detail" || route.query.tab === "results") return "results";
      if (["group-overview", "group-details"].includes(route.name)) return "groups";
    }
    // An attempt can be active or completed; avoid guessing its state from its URL.
    return null;
  });
  return { items, activeKey };
}
