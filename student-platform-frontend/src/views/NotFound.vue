<script setup>
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
</script>
<template><section class="surface-card p-4"><h1>{{ t('ux.notFound') }}</h1><p>{{ t('ux.notFoundCopy') }}</p><router-link class="btn btn-primary" to="/">{{ t('ux.home') }}</router-link></section></template>
