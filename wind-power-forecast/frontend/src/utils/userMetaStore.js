const STORAGE_KEY = 'user_profile_meta_v1'

const safeRead = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch (error) {
    return {}
  }
}

const safeWrite = (value) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(value || {}))
}

export const getAllUserMeta = () => safeRead()

export const getUserMeta = (username) => {
  if (!username) return {}
  const store = safeRead()
  return store[username] || {}
}

export const setUserMeta = (username, meta) => {
  if (!username) return
  const store = safeRead()
  store[username] = {
    ...store[username],
    ...(meta || {})
  }
  safeWrite(store)
}

export const removeUserMeta = (username) => {
  if (!username) return
  const store = safeRead()
  delete store[username]
  safeWrite(store)
}
