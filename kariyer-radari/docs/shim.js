/* Kariyer Radarı · GitHub Pages veri katmanı.
   Pano kodu claude.ai'deki window.claude.use("db") arayüzünü bekler; burada aynı arayüz
   data/*.json dosyalarından okur, senin değişikliklerini (durum, takip) tarayıcıda saklar. */
(function(){
  const PFX="kr2:", OV=PFX+"ov", SAVED=PFX+"saved";
  const ls={get(k,d){try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}},
            set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
  const cache={}, subs={};
  const ov=()=>ls.get(OV,{});              // {"items/ID": {status:"interested"}, "people/ID": {follow:true}}
  async function load(name){
    if(!cache[name]){
      cache[name]=fetch("data/"+name+".json?v="+Date.now(),{cache:"no-store"})
        .then(r=>r.ok?r.json():[]).catch(()=>[]);
    }
    let rows=(await cache[name]).map(x=>Object.assign({},x));
    const o=ov();
    rows.forEach(r=>{const p=o[name+"/"+r.id];if(p)Object.assign(r,p)});
    if(name==="items"){                    // arşivlenmiş ama kaydettiğin kayıtlar kaybolmasın
      const saved=ls.get(SAVED,{}), ids=new Set(rows.map(r=>r.id));
      Object.values(saved).forEach(s=>{if(!ids.has(s.id))rows.push(Object.assign({},s,o["items/"+s.id]||{}))});
    }
    if(name==="sources"){
      rows.forEach(s=>{const h=s.health;if(h&&h.fails>=3)s.name=s.name+" · ⚠ "+h.fails+" taramadır yanıt yok"});
    }
    return rows;
  }
  function query(name){
    let lim=null, ord=null;
    const q={
      limit(n){lim=n;return q}, orderBy(f,dir){ord=[f,dir||"asc"];return q},
      async emit(cb){
        let rows=await load(name);
        if(ord){const [f,d]=ord;rows.sort((a,b)=>((a[f]||"")>(b[f]||"")?1:(a[f]||"")<(b[f]||"")?-1:0)*(d==="desc"?-1:1))}
        if(lim)rows=rows.slice(0,lim);
        cb({docs:rows.map(r=>({id:r.id,data:()=>r}))});
      },
      onSnapshot(cb,err){(subs[name]=subs[name]||[]).push(()=>q.emit(cb));q.emit(cb).catch(e=>err&&err(e));return()=>{}}
    };
    return q;
  }
  const db={
    collection:query,
    doc(path){return{async update(data){
      const o=ov();o[path]=Object.assign(o[path]||{},data);ls.set(OV,o);
      const [col,id]=path.split("/");
      if(col==="items"){
        const saved=ls.get(SAVED,{});
        if(data.status==="interested"||data.status==="applied"){
          const row=(await cache.items||[]).find(r=>r.id===id)||saved[id];
          if(row)saved[id]=Object.assign({},row,data);
        }else delete saved[id];
        ls.set(SAVED,saved);
      }
    }}}
  };
  window.claude={use:async(n)=>n==="db"?db:null};

  // Yedekleme: durumlarını başka cihaza taşımak için
  window.krExport=function(){
    const blob=new Blob([JSON.stringify({ov:ls.get(OV,{}),saved:ls.get(SAVED,{})})],{type:"application/json"});
    const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="kariyer-radari-durumlar.json";a.click();
  };
  window.krImport=function(file){
    const r=new FileReader();r.onload=()=>{try{const d=JSON.parse(r.result);
      ls.set(OV,Object.assign(ls.get(OV,{}),d.ov||{}));ls.set(SAVED,Object.assign(ls.get(SAVED,{}),d.saved||{}));location.reload()}
      catch(e){alert("Dosya okunamadı")}};r.readAsText(file);
  };
  // Son çalışma bilgisi
  fetch("data/meta.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.ok?r.json():null).then(m=>{
    if(!m)return;const el=document.getElementById("runmeta");if(!el)return;
    const d=new Date(m.lastRun);
    el.textContent="Son çalışma: "+d.toLocaleString("tr-TR",{dateStyle:"medium",timeStyle:"short"})+" · "+m.new+" yeni · "+
      m.total+" kayıt · "+(m.jobs-m.errors)+"/"+m.jobs+" kaynak yanıt verdi"+(m.llm?" · YZ özetli":"");
  }).catch(()=>{});
})();
