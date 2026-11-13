"""claude.ai 版 (index.html) から GitHub Pages 版 (docs/index.html) を作る。
みんなの結果の保存先を Supabase に差し替え、ふつうの HTML 文書の形にする。
使い方: python3 tools/build_pages.py
"""
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUPABASE_URL = 'https://glvgumgdwmhaaafstaly.supabase.co'
SUPABASE_KEY = (ROOT / 'supabase' / 'anon_key.txt').read_text().strip() if (ROOT / 'supabase' / 'anon_key.txt').exists() else ''

src = (ROOT / 'index.html').read_text(encoding='utf-8')

def rep(s, old, new):
    assert s.count(old) == 1, old[:60]
    return s.replace(old, new)

# 投稿欄: ニックネーム入力をつける
src = rep(src, '''      <button class="btn btn-primary" id="btnPost" type="button">みんなの結果に載せる</button>
      <p class="small" id="postNote">馬名・出生国・結果・確率と、あなたの名前が、このページを開いた人に表示されます。</p>''',
'''      <div class="namerow nickrow"><label for="nick">ニックネーム</label><input id="nick" type="text" maxlength="12" autocomplete="nickname" placeholder="12文字まで"></div>
      <button class="btn btn-primary" id="btnPost" type="button">みんなの結果に載せる</button>
      <p class="small" id="postNote">ニックネーム・馬名・出生国・結果・確率が、だれでも見られる「みんなの結果」に載ります。</p>''')
src = rep(src, '.post .btn[disabled]{', '.nickrow{margin:0 0 0.2rem;}\n.nickrow label{flex:none; font-weight:700; font-size:0.9rem;}\n.post .btn[disabled]{')

start = src.index('/* ---------- みんなの結果(ネット版: 共有データベース) ---------- */')
end = src.index('// 結果画面にも「みんなの結果」を出す')

NET = r'''/* ---------- みんなの結果(GitHub Pages 版: Supabase) ---------- */
const SB_URL = '__URL__', SB_KEY = '__KEY__';
const NET = {docs:[], stats:null, tab:'new', posted:null, busy:false, ready:false, device:null, mine:new Set()};
const RK_ORDER = ['g1','g2','g3','l','n'];
const S = (v, n) => typeof v === 'string' ? v.slice(0, n) : '';
try {
  NET.device = localStorage.getItem('sb_device');
  if (!NET.device || NET.device.length < 16){ NET.device = (crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')); localStorage.setItem('sb_device', NET.device); }
  const m = JSON.parse(localStorage.getItem('sb_mine') || '[]'); if (Array.isArray(m)) m.forEach(x => NET.mine.add(String(x)));
} catch(e){ if (!NET.device) NET.device = 'tmp-' + Math.random().toString(36).slice(2) + Date.now().toString(36); }
async function sb(path, opts){
  const r = await fetch(SB_URL + path, Object.assign({}, opts, {headers: Object.assign({apikey: SB_KEY, 'Content-Type': 'application/json'}, SB_KEY.startsWith('eyJ') ? {Authorization: 'Bearer ' + SB_KEY} : {}, (opts && opts.headers) || {})}));
  if (!r.ok){ let msg = ''; try { msg = (await r.json()).message || ''; } catch(e){} const err = new Error(msg || ('HTTP ' + r.status)); err.status = r.status; throw err; }
  const t = await r.text(); return t ? JSON.parse(t) : null;
}
const COLS = 'id,created_at,run_id,nick,horse,country,breed,headline,sub,rarity,p';
function cleanRow(x){
  if (!x || typeof x !== 'object') return null;
  const p = Number(x.p), t = Date.parse(x.created_at);
  if (!(p > 0 && p <= 1) || !isFinite(t)) return null;
  return {id:x.id, run:S(x.run_id, 40), nick:S(x.nick, 12) || 'ななし', n:S(x.horse, 9) || 'ノーネーム', c:S(x.country, 20), b:S(x.breed, 20), h:S(x.headline, 20), s:S(x.sub, 40), r: RK_ORDER.includes(x.rarity) ? x.rarity : 'n', p, t};
}
function ago(t){
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return 'たった今'; if (s < 3600) return Math.floor(s / 60) + '分前';
  if (s < 86400) return Math.floor(s / 3600) + '時間前'; if (s < 86400 * 30) return Math.floor(s / 86400) + '日前';
  const d = new Date(t); return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
}
async function loadBoard(){
  if (!SB_KEY) return;
  try {
    const order = NET.tab === 'new' ? 'created_at.desc' : 'p.asc,created_at.desc';
    const [rows, st] = await Promise.all([sb(`/rest/v1/plays?select=${COLS}&order=${order}&limit=30`), sb('/rest/v1/rpc/board_stats', {method:'POST', body:'{}'})]);
    NET.docs = (Array.isArray(rows) ? rows : []).map(cleanRow).filter(Boolean); NET.stats = st; NET.ready = true; renderBoard();
  } catch(e){ if (!NET.ready) boardOffline('みんなの結果を読み込めませんでした。少し待ってから、ページを開き直してください。'); }
}
function renderBoard(){
  if (!NET.ready) return;
  const st = NET.stats || {}, num = v => Number.isFinite(+v) ? +v : 0;
  $('boardStat').textContent = num(st.total) ? `${num(st.players).toLocaleString('ja-JP')}人が、あわせて${num(st.total).toLocaleString('ja-JP')}頭の馬生を載せました。` : 'まだだれも結果を載せていません。';
  const tl = $('boardTally'); tl.innerHTML = '';
  if (num(st.total)) RK_ORDER.forEach(k => { const li = document.createElement('li'); li.textContent = `${RARITY[k].label} ${num(st[k]).toLocaleString('ja-JP')}`; tl.append(li); });
  const feed = $('feed'); feed.innerHTML = '';
  $('feedEmpty').classList.toggle('hidden', NET.docs.length > 0);
  NET.docs.forEach((x, i) => {
    const li = document.createElement('li');
    const rk = document.createElement('span'); rk.className = 'rk rk-' + x.r; rk.textContent = RARITY[x.r].label;
    const nm = document.createElement('span'); nm.className = 'nm';
    if (NET.tab === 'rare'){ const rn = document.createElement('span'); rn.className = 'rank'; rn.textContent = (i + 1) + '位'; nm.append(rn); }
    nm.append(document.createTextNode(x.n));
    const od = document.createElement('span'); od.className = 'odds'; od.textContent = `約${fmtOneIn(x.p)}分の1`;
    const meta = document.createElement('span'); meta.className = 'meta';
    meta.textContent = `${x.c}生まれの${x.b} ／ ` + (x.h === x.b ? (x.s || '') : `${x.h}${x.s ? '(' + x.s + ')' : ''}`) + ' ／ ';
    const who = document.createElement('span');
    if (NET.mine.has(x.run)){ who.className = 'mine'; who.textContent = 'あなた(' + x.nick + ')'; } else who.textContent = x.nick + 'さん';
    meta.append(who, document.createTextNode(' ・ ' + ago(x.t)));
    li.append(rk, nm, od, meta); feed.append(li);
  });
}
function setTab(t){ NET.tab = t; $('tabNew').setAttribute('aria-selected', t === 'new'); $('tabRare').setAttribute('aria-selected', t === 'rare'); loadBoard(); }
$('tabNew').onclick = () => setTab('new');
$('tabRare').onclick = () => setTab('rare');
function boardOffline(msg){ NET.ready = false; $('boardStat').textContent = msg; $('boardTally').innerHTML = ''; $('feed').innerHTML = ''; $('feedEmpty').classList.add('hidden'); }
function initNet(){
  try { const n = localStorage.getItem('sb_nick'); if (n) $('nick').value = n; } catch(e){}
  if (!SB_KEY){ boardOffline('みんなの結果は、準備中です。'); return; }
  loadBoard();
  setInterval(() => { if (!document.hidden) loadBoard(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) loadBoard(); });
}
function updatePostBox(){
  const box = document.getElementById('postBox'); if (!box) return;
  if (!SB_KEY){ box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  try { const n = localStorage.getItem('sb_nick'); if (n && !$('nick').value) $('nick').value = n; } catch(e){}
  const btn = $('btnPost'), note = $('postNote');
  if (NET.posted && NET.posted === life){ btn.textContent = '載せた内容を更新'; note.textContent = 'みんなの結果に載せました。馬名やニックネームを変えたら、もう一度押すと書き換わります。'; }
  else { btn.textContent = 'みんなの結果に載せる'; note.textContent = 'ニックネーム・馬名・出生国・結果・確率が、だれでも見られる「みんなの結果」に載ります。'; }
}
async function postResult(){
  if (!life || NET.busy || !SB_KEY) return;
  const nick = ($('nick').value || '').replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 12);
  if (!nick){ $('postNote').textContent = 'ニックネームを入れてください(12文字まで)。'; $('nick').focus(); return; }
  try { localStorage.setItem('sb_nick', nick); } catch(e){}
  NET.busy = true; const btn = $('btnPost'); btn.disabled = true;
  const horse = (($('horseName').value || '').trim().slice(0, 9)) || life.horseName || 'ノーネーム';
  if (!life.netId) life.netId = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  try {
    await sb('/rest/v1/rpc/post_play', {method:'POST', body: JSON.stringify({p_device:NET.device, p_run:life.netId, p_nick:nick, p_horse:horse, p_country:life.c.ja, p_breed:life.breed, p_headline:life.headline, p_sub:(life.sub || '').slice(0, 40), p_rarity:rarityOf(life), p_p:life.p})});
    NET.mine.add(life.netId); try { localStorage.setItem('sb_mine', JSON.stringify([...NET.mine].slice(-500))); } catch(e){}
    NET.posted = life; sfx.win(); updatePostBox(); loadBoard();
  } catch(e){
    const m = String(e && e.message || '');
    $('postNote').textContent = m.includes('rate_limited') ? '短い時間に載せすぎました。10分ほど待ってから、もう一度押してください。'
      : m.includes('busy') ? 'いま混みあっています。少し待ってから、もう一度押してください。'
      : '載せられませんでした。通信を確かめて、もう一度押してください。';
  } finally { NET.busy = false; btn.disabled = false; }
}

'''.replace('__URL__', SUPABASE_URL).replace('__KEY__', SUPABASE_KEY)
src = src[:start] + NET + src[end:]

# 文書の形にする(<title>〜</style> を head に)
cut = src.index('</style>') + len('</style>')
head, body = src[:cut], src[cut:]
page = ('<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="今年生まれる馬の一頭になって、その一生をたどる非公式のファン作品ゲーム。図鑑・実績・10連馬生・みんなの結果つき。">\n'
        + head + '\n</head>\n<body>\n' + body.strip() + '\n</body>\n</html>\n')
out = ROOT / 'docs' / 'index.html'
out.parent.mkdir(exist_ok=True)
out.write_text(page, encoding='utf-8')
print('wrote', out, len(page), 'key' if SUPABASE_KEY else 'NO KEY')
