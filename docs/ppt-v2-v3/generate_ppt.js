const fs = require('fs');
const path = require('path');
const PptxGenJS = require('/tmp/askdata-ppt-deps/node_modules/pptxgenjs');

const ROOT = __dirname;
const ASSETS = path.join(ROOT, 'assets');
const OUT = path.join(ROOT, 'output');
const FONT = 'Microsoft YaHei';
const C = {
  ink: '182033', muted: '667085', green: '17745F', blue: '5C91C8',
  paleGreen: 'F2F8F6', paleBlue: 'EEF4FA', orange: 'F47C3C',
  line: 'D6E3DF', white: 'FFFFFF', gray: 'F7F9FB', softOrange: 'FFF4EC'
};

function parseDeck(file) {
  const text = fs.readFileSync(file, 'utf8');
  const deckTitle = (text.match(/^#\s+(.+)$/m) || [,''])[1];
  const meta = (text.match(/^>\s+(.+)$/m) || [,''])[1];
  const re = /^##\s+第(\d+)页｜(.+)$/gm;
  const matches = [...text.matchAll(re)];
  const pages = matches.map((m, i) => {
    const body = text.slice(m.index + m[0].length, i + 1 < matches.length ? matches[i+1].index : text.length);
    const images = [...body.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)].map(x => path.join(ROOT, x[1]));
    const tableLines = body.split('\n').filter(x => /^\s*\|/.test(x));
    let table = null;
    if (tableLines.length >= 3) {
      table = tableLines.filter(x => !/^\s*\|?\s*:?-+/.test(x)).map(x => x.trim().replace(/^\||\|$/g,'').split('|').map(y => clean(y)));
    }
    let stripped = body.replace(/!\[[^\]]*\]\([^)]+\)/g, '')
      .replace(/^\s*\|.*$/gm, '').replace(/^###.*$/gm, '')
      .replace(/\*\*(页面文案|文案|核心结论|讲解要点|布局与展示|布局)\*\*[:：]?/g, '$1：');
    const lines = stripped.split('\n').map(clean).filter(Boolean)
      .filter(x => !/^布局(与展示)?[:：]/.test(x));
    return { num: Number(m[1]), title: clean(m[2]), body, images, table, lines };
  });
  return { deckTitle, meta, pages };
}

function clean(s) {
  return String(s || '').replace(/^[-*]\s+/, '').replace(/^\d+[.、]\s*/, '')
    .replace(/\*\*/g, '').replace(/`/g, '').replace(/<[^>]+>/g,'').trim();
}

function addText(slide, text, x, y, w, h, opts={}) {
  slide.addText(text, {x,y,w,h,fontFace:FONT,fontSize:opts.size||18,color:opts.color||C.ink,
    bold:!!opts.bold,breakLine:false,margin:opts.margin===undefined?0.05:opts.margin,
    valign:opts.valign||'mid',align:opts.align||'left',fit:'shrink',paraSpaceAfterPt:opts.after||0,
    bullet:opts.bullet,transparency:opts.transparency||0});
}

function addHeader(slide, p, total, section) {
  addText(slide, String(p.num).padStart(2,'0'), .62, .25, .48, .38, {size:17,bold:true,color:p.num%4===0?C.orange:C.green});
  addText(slide, p.title, 1.18, .17, 9.65, .58, {size:31,bold:true});
  slide.addShape(pptx.ShapeType.roundRect,{x:11.25,y:.26,w:1.46,h:.32,rectRadius:.12,fill:{color:section==='演进规划'?C.softOrange:C.paleGreen},line:{color:section==='演进规划'?C.orange:C.green,width:.8}});
  addText(slide, section, 11.34, .29, 1.28, .22, {size:11,color:section==='演进规划'?C.orange:C.green,align:'center',bold:true});
  slide.addShape(pptx.ShapeType.line,{x:.62,y:.86,w:12.09,h:0,line:{color:C.line,width:1}});
  addText(slide, '企业级智能问数平台', .58, 7.18, 2.5, .16, {size:9,color:'8A96A3'});
  addText(slide, `${p.num} / ${total}`, 11.65, 7.18, 1.08, .16, {size:9,color:'8A96A3',align:'right'});
}

function addCard(slide,x,y,w,h,title,body,i=0) {
  const fills=[C.paleGreen,C.paleBlue,C.gray,C.softOrange];
  slide.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:.08,fill:{color:fills[i%fills.length]},line:{color:i%4===3?'F8C8AA':C.line,width:1},shadow:{type:'outer',color:'A9B8C6',opacity:.16,blur:1.5,angle:45,distance:1}});
  slide.addShape(pptx.ShapeType.ellipse,{x:x+.18,y:y+.19,w:.13,h:.13,fill:{color:i%4===3?C.orange:(i%2?C.blue:C.green)},line:{color:i%4===3?C.orange:(i%2?C.blue:C.green)}});
  addText(slide,title,x+.38,y+.13,w-.55,.38,{size:18,bold:true});
  if(body) addText(slide,body,x+.2,y+.58,w-.4,h-.68,{size:15,color:C.muted,valign:'top',margin:.03});
}

function addImage(slide, file, x,y,w,h) {
  slide.addShape(pptx.ShapeType.roundRect,{x:x-.03,y:y-.03,w:w+.06,h:h+.06,rectRadius:.05,fill:{color:C.white},line:{color:C.line,width:1}});
  if (file.endsWith('.svg')) {
    const svg=fs.readFileSync(file,'utf8')
      .replace(/SimSun,宋体,serif|宋体|Noto Serif CJK SC/g,'Microsoft YaHei,微软雅黑,sans-serif')
      .replace(/font-size\s*:\s*(?:1[0-9]|2[0-3])px/g,'font-size:24px')
      .replace(/font-size\s*=\s*["'](?:1[0-9]|2[0-3])["']/g,'font-size="24"')
      .replace(/font\s*:\s*700\s+(?:1[0-9]|2[0-3])px/g,'font:700 24px');
    const data = 'data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64');
    slide.addImage({data,x,y,w,h,sizing:'contain'});
  } else slide.addImage({path:file,x,y,w,h,sizing:'contain'});
}

function usefulLines(p) {
  return p.lines.filter(x => !/^(页面文案|文案|核心结论|讲解要点)[:：]?$/.test(x))
    .map(x => x.replace(/^(页面文案|文案|核心结论|讲解要点)[:：]\s*/,''))
    .filter(Boolean).slice(0,10);
}

function renderCover(slide, deck, p) {
  slide.background={color:C.white};
  slide.addShape(pptx.ShapeType.rect,{x:8.1,y:0,w:5.24,h:7.5,fill:{color:C.paleBlue},line:{color:C.paleBlue}});
  for(let i=0;i<6;i++){
    slide.addShape(pptx.ShapeType.ellipse,{x:8.65+i*.58,y:1.1+i*.72,w:.18,h:.18,fill:{color:i===2?C.orange:C.green},line:{color:i===2?C.orange:C.green}});
    if(i<5) slide.addShape(pptx.ShapeType.line,{x:8.82+i*.58,y:1.28+i*.72,w:.55,h:.55,line:{color:C.blue,width:2}});
  }
  addText(slide,'ASK DATA / BUSINESS SOLUTION',.72,.64,5.6,.3,{size:12,bold:true,color:C.green});
  const parts = usefulLines(p);
  const title = parts[0] || deck.deckTitle;
  const subtitle = parts[1] || deck.meta;
  addText(slide,title,.72,1.38,6.8,1.65,{size:46,bold:true,valign:'top'});
  addText(slide,subtitle,.75,3.18,6.55,.8,{size:24,color:C.blue,valign:'top'});
  if(parts[2]) addText(slide,parts[2],.75,4.12,6.45,.65,{size:18,color:C.muted,valign:'top'});
  slide.addShape(pptx.ShapeType.line,{x:.75,y:5.25,w:1.1,h:0,line:{color:C.orange,width:4}});
  addText(slide,'汇报单位｜汇报人｜2026年8月',.75,5.48,5.5,.35,{size:14,color:C.muted});
  addText(slide,'产品 V2.0 · V3.0 演进规划',8.72,6.65,3.72,.3,{size:13,bold:true,color:C.green,align:'right'});
}

function renderTable(slide,p,total,section) {
  addHeader(slide,p,total,section);
  const rows=p.table;
  const cols=Math.max(...rows.map(r=>r.length));
  const data=rows.map((r,ri)=>r.map((v)=>({text:v,options:{bold:ri===0,color:ri===0?C.white:C.ink,fill:ri===0?C.green:(ri%2?C.paleBlue:C.white)}})));
  slide.addTable(data,{x:.72,y:1.15,w:11.9,h:5.65,border:{type:'solid',color:C.white,pt:1},
    fontFace:FONT,fontSize:cols>=3?15:17,color:C.ink,margin:.1,valign:'mid',rowH:.55,
    colW:Array(cols).fill(11.9/cols),autoFit:false});
}

function renderImages(slide,p,total,section) {
  addHeader(slide,p,total,section);
  const lines=usefulLines(p);
  if(p.images.length===1){
    const isSvg=p.images[0].endsWith('.svg');
    if(isSvg){
      addImage(slide,p.images[0],.62,1.11,9.18,5.72);
      slide.addShape(pptx.ShapeType.roundRect,{x:10.02,y:1.11,w:2.66,h:5.72,rectRadius:.07,fill:{color:section==='演进规划'?C.softOrange:C.paleGreen},line:{color:section==='演进规划'?C.orange:C.line,width:1},shadow:{type:'outer',color:'A9B8C6',opacity:.14,blur:1.5,angle:45,distance:1}});
      addText(slide,section==='演进规划'?'规划说明':'架构说明',10.25,1.39,2.2,.4,{size:21,bold:true,color:section==='演进规划'?C.orange:C.green});
      const notes=lines.length?lines:[p.title];
      notes.slice(0,4).forEach((t,i)=>{
        addText(slide,String(i+1).padStart(2,'0'),10.25,2.02+i*1.02,.38,.3,{size:14,bold:true,color:i===0?C.orange:C.blue});
        addText(slide,t,10.7,1.86+i*1.02,1.72,.82,{size:17,valign:'top'});
      });
      if(section==='演进规划') addText(slide,'V3.0 规划能力',10.22,6.48,2.18,.24,{size:13,bold:true,color:C.orange,align:'right'});
    } else if(lines.length && lines.join('').length<310){
      const right=p.num%2===1, ix=right?4.52:.66, tx=right?.66:9.46, iw=isSvg?8.15:7.8, tw=right?3.55:3.22;
      addImage(slide,p.images[0],ix,1.11,iw,5.72);
      slide.addShape(pptx.ShapeType.roundRect,{x:tx,y:1.11,w:tw,h:5.72,rectRadius:.07,fill:{color:right?C.paleBlue:C.paleGreen},line:{color:C.line},shadow:{type:'outer',color:'A9B8C6',opacity:.13,blur:1.5,angle:45,distance:1}});
      addText(slide,'本页要点',tx+.25,1.4,tw-.5,.35,{size:20,bold:true,color:C.green});
      lines.slice(0,5).forEach((t,i)=>{
        addText(slide,String(i+1).padStart(2,'0'),tx+.25,1.95+i*.86,.36,.27,{size:13,bold:true,color:i===0?C.orange:C.blue});
        addText(slide,t,tx+.7,1.84+i*.86,tw-.92,.66,{size:15,valign:'top'});
      });
    } else addImage(slide,p.images[0],.7,1.06,11.93,5.85);
  } else {
    addImage(slide,p.images[0],.72,1.17,7.55,5.42);
    addImage(slide,p.images[1],8.48,1.17,4.13,2.72);
    lines.slice(0,4).forEach((t,i)=>addCard(slide,8.48,4.08+i*.63,4.13,.52,t,'',i));
    addText(slide,'演示环境 / 演示数据',8.55,6.68,3.9,.18,{size:10,color:C.orange,align:'right'});
  }
}

function splitLine(t){const m=t.match(/^([^：:｜]{2,14})[：:｜]\s*(.+)$/);return m?[m[1],m[2]]:[t,''];}

function renderFlow(slide,items,y0){
  const n=Math.min(items.length,6), gap=.16,w=(11.9-gap*(n-1))/n;
  items.slice(0,n).forEach((t,i)=>{const [a,b]=splitLine(t);const x=.72+i*(w+gap);
    slide.addShape(pptx.ShapeType.chevron,{x,y:y0,w,h:2.35,fill:{color:i===n-1?C.softOrange:(i%2?C.paleBlue:C.paleGreen)},line:{color:i===n-1?C.orange:(i%2?C.blue:C.green),width:1}});
    addText(slide,String(i+1).padStart(2,'0'),x+.18,y0+.2,w-.36,.32,{size:14,bold:true,color:i===n-1?C.orange:C.green});
    addText(slide,a,x+.18,y0+.67,w-.38,.58,{size:18,bold:true,align:'center'});if(b)addText(slide,b,x+.22,y0+1.3,w-.46,.72,{size:14,color:C.muted,align:'center',valign:'top'});
  });
}

function renderRadial(slide,items,y0){
  const cx=6.66,cy=y0+2.55;
  slide.addShape(pptx.ShapeType.ellipse,{x:5.15,y:cy-.72,w:3.02,h:1.44,fill:{color:C.green},line:{color:C.green},shadow:{type:'outer',color:'80968F',opacity:.2,blur:2,angle:45,distance:1}});
  addText(slide,'统一可信\n能力核心',5.42,cy-.48,2.48,.96,{size:22,bold:true,color:C.white,align:'center'});
  const pts=[[.9,.15],[4.05,.05],[8.55,.05],[10.35,2.4],[8.55,4.15],[4.05,4.15],[.9,3.95],[.15,2.05]];
  items.slice(0,8).forEach((t,i)=>{const [a,b]=splitLine(t),[x,dy]=pts[i];
    slide.addShape(pptx.ShapeType.line,{x:cx,y:cy,w:x+1.15-cx,h:y0+dy+.48-cy,line:{color:C.line,width:1.2}});
    addCard(slide,x,y0+dy,2.3,.96,a,b,i);
  });
}

function renderContrast(slide,items,y0){
  const left=[],right=[];items.forEach((t,i)=>(i%2?right:left).push(t));
  [['现状 / 基线',left,.72,C.paleGreen,C.green],['目标 / 演进',right,6.84,C.paleBlue,C.blue]].forEach(([head,arr,x,fill,color])=>{
    slide.addShape(pptx.ShapeType.roundRect,{x,y:y0,w:5.78,h:4.75,rectRadius:.08,fill:{color:fill},line:{color,width:1.2}});
    addText(slide,head,x+.3,y0+.22,5.18,.42,{size:22,bold:true,color});
    arr.slice(0,4).forEach((t,i)=>{addText(slide,'●',x+.32,y0+.93+i*.88,.22,.28,{size:12,color:i===0?C.orange:color});addText(slide,t,x+.68,y0+.82+i*.88,4.72,.58,{size:16,valign:'top'});});
  });
  slide.addShape(pptx.ShapeType.chevron,{x:6.28,y:y0+1.95,w:.58,h:.72,fill:{color:C.orange},line:{color:C.orange}});
}

function renderCards(slide,p,total,section) {
  addHeader(slide,p,total,section);
  const ls=usefulLines(p);
  let lead=''; let items=ls;
  if(ls.length>1 && (ls[0].length>28 || /定位|结论|愿景/.test(ls[0]))){lead=ls[0];items=ls.slice(1);}
  if(lead){
    slide.addShape(pptx.ShapeType.roundRect,{x:.72,y:1.08,w:11.9,h:.82,rectRadius:.05,fill:{color:C.paleGreen},line:{color:C.line}});
    addText(slide,lead,1.02,1.24,11.3,.46,{size:18,bold:true,color:C.green,align:'center'});
  }
  const y0=lead?2.14:1.18;
  if(/路径|流程|路线|阶段|下一步/.test(p.title)){renderFlow(slide,items,y0+.55);return;}
  if(/定位|背景|挑战|为什么|边界/.test(p.title) && items.length>=4){renderContrast(slide,items,y0);return;}
  if(/全景|目标用户|优势|价值|能力/.test(p.title) && items.length>=5){renderRadial(slide,items,y0-.02);return;}
  const n=Math.min(items.length||1,8); const cols=n<=4?2:(n<=6?3:4); const rows=Math.ceil(n/cols);
  const gap=.22,w=(11.9-gap*(cols-1))/cols,h=Math.min(1.6,(5.72-gap*(rows-1))/rows);
  for(let i=0;i<n;i++){
    const t=items[i]||p.title;
    const split=t.match(/^([^：:｜]{2,12})[：:｜]\s*(.+)$/);
    addCard(slide,.72+(i%cols)*(w+gap),y0+Math.floor(i/cols)*(h+gap),w,h,split?split[1]:t,split?split[2]:'',i);
  }
  if(!items.length) addCard(slide,.72,y0,11.9,2,p.title,'',0);
}

function sectionLabel(title){
  if(/V3|演进|下一步|路线/.test(title)) return '演进规划';
  if(/安全|部署|技术|运维|验收|实施|基线/.test(title)) return '客户适配';
  if(/用户|管理|场景|配置|能力/.test(title)) return '产品能力';
  return '业务方案';
}

async function build(file,outName){
  const deck=parseDeck(file); const globalPptx=new PptxGenJS();
  global.pptx=globalPptx;
  globalPptx.layout='LAYOUT_WIDE'; globalPptx.author='AskData'; globalPptx.company='AskData';
  globalPptx.subject=deck.deckTitle; globalPptx.title=deck.deckTitle; globalPptx.lang='zh-CN'; globalPptx.theme={headFontFace:FONT,bodyFontFace:FONT,lang:'zh-CN'};
  for(const p of deck.pages){
    const slide=globalPptx.addSlide(); slide.background={color:C.white};
    const section=sectionLabel(p.title);
    if(p.num===1) renderCover(slide,deck,p);
    else if(p.table) renderTable(slide,p,deck.pages.length,section);
    else if(p.images.length) renderImages(slide,p,deck.pages.length,section);
    else renderCards(slide,p,deck.pages.length,section);
    slide.addNotes(`来源：${path.basename(file)}，第${p.num}页。所有文字与形状可在PowerPoint中编辑。`);
  }
  fs.mkdirSync(OUT,{recursive:true});
  await globalPptx.writeFile({fileName:path.join(OUT,outName)});
  return {outName,pages:deck.pages.length};
}

(async()=>{
  const jobs=[
    ['01-产品V2.0业务方案与V3.0规划-标准完整版.md','01-企业级智能问数平台-标准完整版-新版可编辑.pptx'],
    ['02-产品V2.0业务方案与V3.0规划-领导汇报版.md','02-企业级智能问数平台-领导汇报版-新版可编辑.pptx'],
    ['03-产品V2.0业务方案与V3.0规划-客户交流版.md','03-企业级智能问数平台-客户交流版-新版可编辑.pptx']
  ];
  for(const [src,out] of jobs) console.log(await build(path.join(ROOT,src),out));
})().catch(e=>{console.error(e);process.exit(1)});
