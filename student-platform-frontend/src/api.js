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

export let Topic = apiConstructor("/api/topic/");
export let Group = apiConstructor("/api/group/");
export let Users = apiConstructor("/api/user/");
