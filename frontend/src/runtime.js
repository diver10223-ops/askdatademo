export const isOffline = location.protocol === 'file:' ||
    location.pathname.endsWith('/askdata-offline.html') ||
    new URLSearchParams(location.search).has('offline');
