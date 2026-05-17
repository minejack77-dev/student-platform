export const datasetUrl = "/api/dataset/";

import axios from "axios";

export default function toURLParams(filters) {
  let params = new URLSearchParams();
  for (let f in filters) {
    if (Array.isArray(filters[f])) {
      for (let p of filters[f]) {
        if (p) {
          params.append(f, p);
        }
      }
    } else if (filters[f] && filters[f].id) {
      params.append(f, filters[f]["id"]);
    } else {
      if (filters[f] != undefined) {
        params.append(f, filters[f]);
      }
    }
  }
  return params;
}

async function _save(url, obj) {
  let response;
  if (obj.id) {
    response = await axios.patch(url + obj.id + "/", obj);
  } else {
    response = await axios.post(url, obj);
  }
  return response.data;
}

async function _delete(url, obj) {
  let response;
  if (obj.id) {
    response = await axios.delete(url + obj.id + "/", obj);
  }

  return response;
}

async function _getList(url, filter) {
  const response = await axios.get(url + "?" + toURLParams(filter));
  return response.data;
}

async function _getById(url, id) {
  const response = await axios.get(url + id + "/");
  return response.data;
}

function apiConstructor(apiUrl) {
  return {
    async save(obj) {
      return _save(apiUrl, obj);
    },
    async get(obj) {
      return _getById(apiUrl, obj);
    },
    async filter(filter) {
      return _getList(apiUrl, filter);
    },
    async delete(obj) {
      return _delete(apiUrl, obj);
    },
  };
}

const groupApi = apiConstructor("/api/group/");
groupApi.getTeacherAssignment = async (groupId) => {
  const response = await axios.get(`/api/group/${groupId}/teacher-assignment/`);
  return response.data;
};
groupApi.saveTeacherAssignment = async (groupId, payload) => {
  const response = await axios.patch(
    `/api/group/${groupId}/teacher-assignment/`,
    payload,
  );
  return response.data;
};
groupApi.clearTeacherAssignment = async (groupId) => {
  await axios.delete(`/api/group/${groupId}/teacher-assignment/`);
};
groupApi.getTopicCalendar = async (groupId, params) => {
  const response = await axios.get(`/api/group/${groupId}/topic-calendar/`, { params });
  return response.data;
};
groupApi.saveTopicCalendarItem = async (groupId, payload) => {
  const response = await axios.patch(`/api/group/${groupId}/topic-calendar/`, payload);
  return response.data;
};
groupApi.clearTopicCalendarItem = async (groupId, params) => {
  await axios.delete(`/api/group/${groupId}/topic-calendar/`, {
    params: typeof params === "string" ? { date: params } : params,
  });
};

export let Subject = apiConstructor("/api/subject/");
export let Topic = apiConstructor("/api/topic/");
const taskApi = apiConstructor("/api/task/");
taskApi.importQuestions = async (taskId, payload) => {
  const response = await axios.post(`/api/task/${taskId}/import-questions/`, payload, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};
export let Task = taskApi;
export let Question = apiConstructor("/api/question/");
export let Group = groupApi;
const studentApi = apiConstructor("/api/student/");
studentApi.meAssignments = async () => {
  const response = await axios.get("/api/student/me-assignments/");
  return response.data;
};
studentApi.getScheduledAssignments = async (params) => {
  const response = await axios.get("/api/student/me-assignments/", { params });
  return response.data;
};
export let Student = studentApi;
export let Users = apiConstructor("/api/user/");
export let Attempt = apiConstructor("/api/attempt/");
export let AttemptQuestion = apiConstructor("/api/attempt_question/");
export let Answer = apiConstructor("/api/answer/");

export const Auth = {
  async fetchCsrf() {
    await axios.get("/api/auth/csrf/");
  },
  async login(credentials) {
    const response = await axios.post("/api/auth/login/", credentials);
    return response.data;
  },
  async logout() {
    await axios.post("/api/auth/logout/");
  },
  async me() {
    const response = await axios.get("/api/auth/me/");
    return response.data;
  },
};
