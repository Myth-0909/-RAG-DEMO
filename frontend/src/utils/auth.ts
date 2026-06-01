export const getToken = () => localStorage.getItem('token');

export const setToken = (token: string) => localStorage.setItem('token', token);

export const removeToken = () => localStorage.removeItem('token');

export const isAuthenticated = () => !!getToken();

export const getUserInfo = () => {
  const info = localStorage.getItem('userInfo');
  return info ? JSON.parse(info) : null;
};

export const setUserInfo = (info: any) => localStorage.setItem('userInfo', JSON.stringify(info));
