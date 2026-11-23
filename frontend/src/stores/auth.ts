import { defineStore } from "pinia";
import { ref } from "vue";

export type UserPublic = {
  id: number;
  username: string;
  email: string;
  nickname: string;
  avatar_url: string | null;
  points: number;
  invite_code?: string | null;
};

const RT_KEY = "dj_refresh_token";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("dj_token"));
  const refreshToken = ref<string | null>(localStorage.getItem(RT_KEY));
  const user = ref<UserPublic | null>(null);

  function setAccessToken(t: string) {
    token.value = t;
    localStorage.setItem("dj_token", t);
  }

  function setSession(access: string, u: UserPublic, refresh?: string | null) {
    token.value = access;
    user.value = u;
    localStorage.setItem("dj_token", access);
    if (refresh) {
      refreshToken.value = refresh;
      localStorage.setItem(RT_KEY, refresh);
    }
  }

  function clear() {
    token.value = null;
    refreshToken.value = null;
    user.value = null;
    localStorage.removeItem("dj_token");
    localStorage.removeItem(RT_KEY);
  }

  return { token, refreshToken, user, setSession, setAccessToken, clear };
});
