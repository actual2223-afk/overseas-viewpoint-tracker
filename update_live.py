"""Discover new public RSS items for the opinion radar.
This updater never promotes RSS metadata into a verified opinion card.
The checked card snapshot is curated separately in data/latest.json.
"""
import hashlib,html,json,re,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'latest.json'
FEEDS=[('a16z','https://feeds.simplecast.com/JGE3yC0V'),('高盛','https://feeds.megaphone.fm/GLD9218176758')]
UA='OpinionRadar/1.0 (public RSS research; contact via repository issues)'

def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',s or ''))).strip()
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml, application/xml, text/xml'})
 with urllib.request.urlopen(req,timeout=18) as r:
  if r.status!=200:raise ValueError('HTTP '+str(r.status))
  raw=r.read(15_000_001)
  if len(raw)>15_000_000:raise ValueError('feed too large')
  return raw

def episodes(raw):
 root=ET.fromstring(raw)
 for i in root.findall('.//item'):
  def field(name):return (i.findtext(name) or '').strip()
  title=clean(field('title'));desc=clean(field('description'))
  link=field('link') or field('guid')
  if not link.startswith('https://'):
   enclosure=i.find('enclosure')
   link=enclosure.get('url','') if enclosure is not None else ''
  if not link.startswith('https://'):continue
  try:dt=parsedate_to_datetime(field('pubDate')).astimezone(timezone.utc)
  except (TypeError,ValueError):continue
  yield title,desc,link,dt

def main():
 d=json.loads(DATA.read_text(encoding='utf-8'));now=datetime.now(timezone.utc)
 old={x['id']:x for x in d.get('leads',[]) if x.get('id')}
 results=[];fresh=[]
 for entity,url in FEEDS:
  try:
   n=0
   for title,desc,link,when in episodes(fetch(url)):
    if when<now-timedelta(days=30) or when>now+timedelta(days=2):continue
    hit=(re.search(r'\b(Marc Andreessen|Ben Horowitz)\b',title+' '+desc,re.I) if entity=='a16z' else re.search(r'\b(2027|outlook|AI|artificial intelligence|China|Chinese|economy|economic|Fed|inflation|equit(y|ies)|S&P|oil|Hatzius|Oppenheimer|Snider|Mericle|Struyven)\b',title+' '+desc,re.I))
    if not hit:continue
    n+=1
    key='LIVE-'+hashlib.sha256(link.encode()).hexdigest()[:12]
    if key in old:continue
    lead={'id':key,'date':when.date().isoformat(),'title':title,'description':'官方 RSS 标题/简介：'+desc[:230],'url':link,'reason':'新发现线索：仅核到 RSS 元数据，正文/音频说话人尚未核验，不能列为正式观点。','entity':entity}
    old[key]=lead;fresh.append(lead)
   results.append({'entity':entity,'status':'成功','relevant_items':n,'checked_at':now.isoformat(),'feed':url})
  except Exception as exc:
   results.append({'entity':entity,'status':'失败','error':type(exc).__name__+': '+str(exc)[:120],'checked_at':now.isoformat(),'feed':url})
 good=sum(x['status']=='成功' for x in results)
 if good:
  d['leads']=sorted(old.values(),key=lambda x:x.get('date',''),reverse=True)[:80]
  d['last_successful_check']=now.strftime('%Y-%m-%d %H:%M UTC')
  d['mode']='自动发现已运行；正式观点卡仍为人工构建的已核快照'+('；部分信源失败' if good<len(FEEDS) else '')
  d['feed_checks']=results
 else:
  d['mode']='本轮信源全部失败；展示上次成功快照'
  d['feed_checks']=results
 d['generated_at']=now.isoformat()
 DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'successful_feeds':good,'new_leads':len(fresh),'checks':results},ensure_ascii=False))
 # Failed feeds remain visible and cannot be interpreted as zero new items.
if __name__=='__main__':main()
