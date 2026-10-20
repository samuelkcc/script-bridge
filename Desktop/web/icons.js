// Original line symbols; no icon font or remote assets.
const paths={
 bridge:'<path d="M3 8h12m-4-4 4 4-4 4M21 16H9m4-4-4 4 4 4"/>',
 home:'<path d="m3 10 9-7 9 7v10H3zM9 20v-7h6v7"/>',
 code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
 book:'<path d="M12 5v16M3 3h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5v16h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3z"/>',
 compass:'<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6z"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 1 1 5 2c-1 1-2 1-2 3m0 2v1"/>',
 arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
 back:'<path d="M20 12H4m6-6-6 6 6 6"/>',
 check:'<path d="m5 12 4 4L19 6"/>',
 shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
 clipboard:'<rect x="5" y="5" width="14" height="16" rx="2"/><rect x="9" y="2" width="6" height="6" rx="1"/>',
 clipboardOut:'<path d="M9 4H6a2 2 0 0 0-2 2v14h12v-3M15 4h2v5"/><rect x="8" y="2" width="6" height="5" rx="1"/><path d="M10 13h11m-4-4 4 4-4 4"/>',
 file:'<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h6"/>',
 sparkle:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
 close:'<path d="m6 6 12 12M6 18 18 6"/>',
 search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
 warning:'<path d="m12 3 10 18H2zM12 9v5m0 3v1"/>',
 external:'<path d="M14 3h7v7m0-7L10 14M11 3H3v18h18v-8"/>',
 heart:'<path d="M12 21 3.5 12.5C-3 5.5 7 0 12 7c5-7 15-1.5 8.5 5.5z"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 4v3"/>',
 moon:'<path d="M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10z"/>'
};
export function icon(name){return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.file}</svg>`;}
export function hydrateIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
