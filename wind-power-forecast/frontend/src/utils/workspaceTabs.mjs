export function getWorkspaceTabKey(route) {
  return String(route?.name || route?.path || '')
}

export function routeToWorkspaceTab(route) {
  const key = getWorkspaceTabKey(route)
  if (!key || !route?.name || route.name === 'Login' || route?.path === '/login') return null

  const path = String(route?.path || '/')
  return {
    key,
    name: typeof route?.name === 'string' ? route.name : '',
    path,
    fullPath: String(route?.fullPath || path),
    title: String(route?.meta?.title || route?.name || path),
    closable: route?.meta?.affix !== true
  }
}

export function upsertWorkspaceTab(tabs, route) {
  const nextTab = routeToWorkspaceTab(route)
  const currentTabs = Array.isArray(tabs) ? tabs : []
  if (!nextTab) return [...currentTabs]

  const index = currentTabs.findIndex(tab => tab.key === nextTab.key)
  if (index < 0) return [...currentTabs, nextTab]

  const nextTabs = [...currentTabs]
  nextTabs[index] = {
    ...nextTabs[index],
    ...nextTab,
    closable: nextTabs[index].closable !== false && nextTab.closable !== false
  }
  return nextTabs
}

export function closeWorkspaceTab(tabs, key, activeKey) {
  const currentTabs = Array.isArray(tabs) ? tabs : []
  const index = currentTabs.findIndex(tab => tab.key === key)
  const target = currentTabs[index]

  if (!target || target.closable === false) {
    return { tabs: [...currentTabs], nextTab: null }
  }

  const nextTabs = currentTabs.filter(tab => tab.key !== key)
  if (key !== activeKey) return { tabs: nextTabs, nextTab: null }

  return {
    tabs: nextTabs,
    nextTab: nextTabs[index] || nextTabs[index - 1] || nextTabs[0] || null
  }
}

export function restoreWorkspaceTabs(rawTabs, resolveRoute) {
  if (!Array.isArray(rawTabs) || typeof resolveRoute !== 'function') return []

  return rawTabs.reduce((tabs, storedTab) => {
    try {
      const resolved = resolveRoute(storedTab?.fullPath || storedTab?.path || '/')
      return upsertWorkspaceTab(tabs, resolved)
    } catch {
      return tabs
    }
  }, [])
}
