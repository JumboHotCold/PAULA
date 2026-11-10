export const frontendBuild=Object.freeze(typeof __PAULA_FRONTEND_BUILD__==='undefined'
  ? {git_commit:null,source_digest:null,build_source:'unknown',worktree_dirty:null}
  : __PAULA_FRONTEND_BUILD__);

export function exposeBuildStamp(target=globalThis) {
  if (!Object.hasOwn(target,'__PAULA_BUILD__')) Object.defineProperty(target,'__PAULA_BUILD__',{value:frontendBuild,writable:false,configurable:false});
  console.info('[PAULA frontend build]',frontendBuild);
  return frontendBuild;
}
