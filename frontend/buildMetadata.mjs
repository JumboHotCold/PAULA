import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync,readdirSync,readFileSync } from 'node:fs';
import { dirname,join,relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultRoot=dirname(fileURLToPath(import.meta.url));
export function frontendStamp({root=defaultRoot,revision=process.env.VITE_PAULA_BUILD_COMMIT || process.env.GITHUB_SHA}={}) {
  let source=revision?'environment':'unknown',dirty=null;
  if (!revision) {
    try { revision=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();source='git'; }
    catch { revision=null; }
  }
  if (!/^[a-f0-9]{40}$/i.test(revision||'')) { revision=null;source='unknown'; }
  try { dirty=Boolean(execFileSync('git',['status','--porcelain','--untracked-files=all','--','.'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim()); }
  catch { /* Unknown metadata remains explicit. */ }
  const files=[];
  function visit(dir) {
    if (!existsSync(dir)) return;
    for (const item of readdirSync(dir,{withFileTypes:true})) {
      const path=join(dir,item.name);
      if (item.isDirectory()) visit(path);
      else if (/\.(jsx?|css|json)$/.test(item.name)&&!item.name.includes('.test.')) files.push(path);
    }
  }
  visit(join(root,'src'));
  for (const name of ['index.html','package.json','package-lock.json','vite.config.js','buildMetadata.mjs']) if(existsSync(join(root,name))) files.push(join(root,name));
  const hash=createHash('sha256');
  for(const path of files.sort()) hash.update(relative(root,path).replaceAll('\\','/')).update('\0').update(readFileSync(path,'utf8').replaceAll('\r\n','\n')).update('\0');
  return Object.freeze({git_commit:revision,build_source:source,source_digest:hash.digest('hex'),worktree_dirty:dirty});
}

export function buildStampPlugin(stamp) {
  return {name:'paula-build-stamp',
    configureServer(server) {server.middlewares.use('/__paula_build',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(stamp));});},
    generateBundle(_options,bundle) {
      const assets={};
      for(const [name,item] of Object.entries(bundle)) assets[name]=createHash('sha256').update(item.type==='chunk'?item.code:item.source).digest('hex');
      this.emitFile({type:'asset',fileName:'paula-build.json',source:JSON.stringify({...stamp,assets},null,2)});
    }};
}
