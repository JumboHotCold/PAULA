// Presentation only: preserve source wording, numbering and college headings.
export function messageBlocks(text='') {
  const blocks=[];
  for (const line of String(text).split('\n')) {
    const match=line.match(/^(\s*)(?:(\d+)\.\s+|[-*]\s+)(.*)$/);
    if (match) {
      const ordered=Boolean(match[2]);let block=blocks.at(-1);
      if (block?.type!=='list'||block.ordered!==ordered) {block={type:'list',ordered,items:[]};blocks.push(block);}
      block.items.push({text:match[3],indent:match[1].length,number:ordered?Number(match[2]):undefined});
    } else blocks.push(line.trim()?{type:'paragraph',text:line}:{type:'space'});
  }
  return blocks;
}
