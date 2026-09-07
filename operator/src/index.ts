import 'dotenv/config'
import Fastify, { FastifyRequest } from 'fastify'
import { Pool } from 'pg'
import crypto from 'node:crypto'
import pino from 'pino'
import makeWASocket, { BufferJSON, DisconnectReason, fetchLatestBaileysVersion, initAuthCreds, proto, downloadMediaMessage } from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'
import QRCode from 'qrcode'

type Account = { id:string; accountKey:string; phone:string|null; sock:any; qr:string|null; connection:string; reconnectTimer:NodeJS.Timeout|null; generation:number }
const env={port:Number(process.env.PORT||3001),db:process.env.DATABASE_URL!,apiKey:process.env.OPERATOR_API_KEY||'',webhookSecret:process.env.WEBHOOK_SECRET||'',webhookUrl:process.env.MAIN_APP_WEBHOOK_URL!,mediaUrl:process.env.MAIN_APP_MEDIA_URL!,appEnv:process.env.APP_ENV||'development',qrTtl:Number(process.env.QR_TTL_MS||240000),base:Number(process.env.RECONNECT_BASE_MS||1000),max:Number(process.env.RECONNECT_MAX_MS||30000),mediaMax:Number(process.env.MEDIA_MAX_BYTES||67108864)}
const log=pino({level:process.env.LOG_LEVEL||'info'})
const pool=new Pool({connectionString:env.db,max:10,idleTimeoutMillis:30000})
const sockets=new Map<string,Account>()

function auth(req:FastifyRequest){const supplied=String(req.headers['x-api-key']||''); const a=Buffer.from(supplied); const b=Buffer.from(env.apiKey); if(!b.length || a.length!==b.length || !crypto.timingSafeEqual(a,b)) throw Object.assign(new Error('unauthorized'),{statusCode:401})}
function jid(phone:string){return `${phone.replace(/\D/g,'')}@s.whatsapp.net`}
async function accountRow(accountKey:string){let r=await pool.query('select * from wa_accounts where account_key=$1',[accountKey]); if(r.rowCount) return r.rows[0]; r=await pool.query("insert into wa_accounts(account_key,status) values($1,'stopped') returning *",[accountKey]); return r.rows[0]}

async function loadAuth(accountId:string){
  const cr=await pool.query('select value from wa_auth_creds where account_id=$1',[accountId])
  const creds=cr.rowCount?JSON.parse(cr.rows[0].value,BufferJSON.reviver):initAuthCreds()
  const keys={get:async(type:any,ids:string[])=>{const r=await pool.query('select key_id,value from wa_auth_keys where account_id=$1 and key_type=$2 and key_id=any($3::text[])',[accountId,type,ids]);const out:any={};for(const id of ids){const row=r.rows.find(x=>x.key_id===id);if(row){let v=JSON.parse(row.value,BufferJSON.reviver);if(type==='app-state-sync-key')v=proto.Message.AppStateSyncKeyData.fromObject(v);out[id]=v}}return out},set:async(data:any)=>{for(const [type,values] of Object.entries(data)){for(const [id,value] of Object.entries(values as any)){if(value==null){await pool.query('delete from wa_auth_keys where account_id=$1 and key_type=$2 and key_id=$3',[accountId,type,id]);}else{const json=JSON.stringify(value,BufferJSON.replacer);await pool.query('insert into wa_auth_keys(account_id,key_type,key_id,value) values($1,$2,$3,$4::jsonb) on conflict(account_id,key_type,key_id) do update set value=excluded.value,updated_at=now()',[accountId,type,id,json])}}}}}
  return {state:{creds,keys},saveCreds:async()=>{const json=JSON.stringify(creds,BufferJSON.replacer);await pool.query('insert into wa_auth_creds(account_id,value) values($1,$2::jsonb) on conflict(account_id) do update set value=excluded.value,updated_at=now()',[accountId,json])}}
}

async function signedPost(url:string, body:Buffer|string, contentType:string, extra:Record<string,string>={}):Promise<any>{
 const raw=typeof body==='string'?Buffer.from(body):body
 const sig=crypto.createHmac('sha256',env.webhookSecret).update(raw).digest('hex')
 const r=await fetch(url,{method:'POST',headers:{'content-type':contentType,'x-webhook-signature':sig,...extra},body:raw})
 const text=await r.text(); let parsed:any={}; try{parsed=JSON.parse(text)}catch{}
 if(!r.ok)throw Object.assign(new Error(`main endpoint ${r.status}: ${text.slice(0,300)}`),{status:r.status})
 return parsed
}

async function postWithRetry(url:string, body:string, attempts=3):Promise<any>{
 let last:any
 for(let i=0;i<attempts;i++){
  try{return await signedPost(url,body,'application/json')}catch(err:any){last=err;const status=Number(err?.status||0);if(status>=400 && status<500)throw err;await new Promise(r=>setTimeout(r,Math.min(5000,250*Math.pow(2,i))))}
 }
 throw last
}

async function forward(account:Account,message:any){
 const body=JSON.stringify({event:'message',account_id:account.accountKey,account_jid:account.phone?jid(account.phone):null,message})
 return postWithRetry(env.webhookUrl,body)
}

async function forwardReceipt(account:Account, update:any){
 const key=update?.key||{}; const status=Number(update?.update?.status||0)
 const statusMap:any={1:'pending',2:'sent',3:'delivered',4:'read',5:'played'}
 const body=JSON.stringify({event:'receipt',account_id:account.accountKey,account_jid:account.phone?jid(account.phone):null,receipt:{message_id:key.id,status:statusMap[status]||'unknown',raw_status:status,remote_jid:key.remoteJid||null,from_me:!!key.fromMe}})
 return postWithRetry(env.webhookUrl + '/receipt',body)
}

function mediaDescriptor(msg:any){
 const m=msg.message||{}; const key=msg.key||{};
 const candidates:[string,any][]=[['image',m.imageMessage],['video',m.videoMessage],['audio',m.audioMessage],['document',m.documentMessage],['sticker',m.stickerMessage]]
 const found=candidates.find(([,v])=>!!v); if(!found)return null
 const [type,node]=found; const hash=node.fileSha256?Buffer.from(node.fileSha256).toString('base64'):null
 return {type,media_id:hash, mime_type:node.mimetype||null, filename:node.fileName||null, caption:node.caption||null,
   media_metadata:{file_length:node.fileLength||null,width:node.width||null,height:node.height||null,duration:node.seconds||null,ptt:node.ptt||false,view_once:!!key.isViewOnce}}
}

async function forwardMedia(account:Account,msg:any,mediaId:string){
 const buffer=await downloadMediaMessage(msg,'buffer',{}, {logger:log.child({accountKey:account.accountKey}),reuploadRequest:account.sock!.updateMediaMessage}) as Buffer
 if(buffer.length>env.mediaMax)throw new Error(`media exceeds operator limit ${buffer.length}`)
 return signedPost(`${env.mediaUrl}/${mediaId}`,buffer,'application/octet-stream',{'x-media-mime':String(msg.message?.imageMessage?.mimetype||msg.message?.videoMessage?.mimetype||msg.message?.audioMessage?.mimetype||msg.message?.documentMessage?.mimetype||msg.message?.stickerMessage?.mimetype||'application/octet-stream')})
}


function normalizeMessage(msg:any){const remote=msg.key.remoteJid||'';const from=remote.endsWith('@s.whatsapp.net')?remote.split('@')[0]:remote;const m=msg.message||{};let type='text',body='';const media=mediaDescriptor(msg);if(m.conversation)body=m.conversation;else if(m.extendedTextMessage?.text)body=m.extendedTextMessage.text;else if(m.locationMessage){type='location';return{id:msg.key.id,from,from_e164:`+${from}`,type,body:'location',latitude:m.locationMessage.degreesLatitude,longitude:m.locationMessage.degreesLongitude,push_name:msg.pushName}}else if(m.buttonsResponseMessage?.selectedButtonId){type='interactive';body=m.buttonsResponseMessage.selectedButtonId}else if(m.listResponseMessage?.singleSelectReply?.selectedRowId){type='interactive';body=m.listResponseMessage.singleSelectReply.selectedRowId}else if(media){type=media.type;body=media.caption||'';return{id:msg.key.id,from,from_e164:`+${from}`,type,body,push_name:msg.pushName,media_id:media.media_id,mime_type:media.mime_type,filename:media.filename,media_metadata:media.media_metadata}}return{id:msg.key.id,from,from_e164:`+${from}`,type,body,push_name:msg.pushName}}


async function start(accountKey:string,delay=0){
 const row=await accountRow(accountKey);const existing=sockets.get(accountKey);if(existing?.reconnectTimer){clearTimeout(existing.reconnectTimer);existing.reconnectTimer=null} 
 const generation=(existing?.generation||0)+1;const account:Account={id:row.id,accountKey,phone:row.phone_e164,sock:null,qr:null,connection:'connecting',reconnectTimer:null,generation};sockets.set(accountKey,account)
 if(delay){await new Promise(r=>setTimeout(r,delay));if(sockets.get(accountKey)?.generation!==generation)return}
 const {state,saveCreds}=await loadAuth(row.id);const {version,isLatest}=await fetchLatestBaileysVersion();log.info({accountKey,version,isLatest},'Resolved WhatsApp Web version')
 const sock=makeWASocket({auth:state,version,printQRInTerminal:false,browser:['NahaLabs','Chrome','120.0.0.0'],qrTimeout:20000,markOnlineOnConnect:true,logger:log.child({accountKey}),shouldSyncHistoryMessage:()=>false});account.sock=sock
 sock.ev.on('creds.update',saveCreds)
 sock.ev.on('connection.update',async(update:any)=>{const {connection,lastDisconnect,qr}=update;if(qr){account.qr=qr;await pool.query("update wa_accounts set qr_code=$1,qr_created_at=now(),connection_state='connecting',status='pairing',updated_at=now() where id=$2",[qr,row.id]);log.info({accountKey},'QR generated')}
   if(connection==='open'){account.connection='open';account.qr=null;account.phone=sock.user?.id?.split(':')[0]?.split('@')[0]||account.phone;await pool.query("update wa_accounts set status='connected',connection_state='open',qr_code=null,last_connected_at=now(),updated_at=now() where id=$1",[row.id]);log.info({accountKey},'WhatsApp connected');return}
   if(connection==='close'){const statusCode=(lastDisconnect?.error as Boom)?.output?.statusCode;log.warn({accountKey,statusCode,message:lastDisconnect?.error?.message},'WhatsApp socket closed');if(sockets.get(accountKey)?.sock!==sock)return;if(statusCode===DisconnectReason.loggedOut||statusCode===500){await pool.query("delete from wa_auth_creds where account_id=$1",[row.id]);await pool.query("delete from wa_auth_keys where account_id=$1",[row.id]);await pool.query("update wa_accounts set status='stopped',connection_state='close',qr_code=null,last_disconnect_at=now(),last_disconnect_code=$2,last_disconnect_message=$3,updated_at=now() where id=$1",[row.id,statusCode,lastDisconnect?.error?.message||'logged out']);account.connection='close';return}
     if(statusCode===DisconnectReason.connectionReplaced)return; const wait=Math.min(env.max,env.base*Math.max(1,2**Math.min(5,(account.generation%6))))+Math.floor(Math.random()*500);account.reconnectTimer=setTimeout(()=>void start(accountKey,wait),wait);await pool.query("update wa_accounts set status='reconnecting',connection_state='close',last_disconnect_at=now(),last_disconnect_code=$2,last_disconnect_message=$3,updated_at=now() where id=$1",[row.id,statusCode,lastDisconnect?.error?.message||'closed'])
   }} )
 sock.ev.on('messages.upsert',async({messages,type}:any)=>{if(type!=='notify')return;for(const msg of messages){if(msg.key.fromMe||!msg.message||msg.requestId)continue;try{const normalized=normalizeMessage(msg);const response=await forward(account,normalized);const mediaId=response?.media_ids?.[0];if(mediaId && normalized.type!=='text' && normalized.type!=='location' && normalized.type!=='interactive'){try{await forwardMedia(account,msg,String(mediaId));log.info({accountKey,mediaId,messageId:normalized.id},'Inbound media downloaded and uploaded')}catch(mediaErr){log.error({err:mediaErr,accountKey,mediaId,messageId:normalized.id},'Failed downloading/uploading inbound media')}}}catch(err){log.error({err,accountKey},'Failed forwarding inbound message')}}})
 sock.ev.on('messages.update',async(updates:any[])=>{for(const update of updates){try{await forwardReceipt(account,update)}catch(err){log.error({err,accountKey,messageId:update?.key?.id},'Failed forwarding delivery receipt')}}})
}

const app=Fastify({logger:log})
app.get('/healthz',async()=>({status:'ok',service:'naha-whatsapp-operator',accounts:sockets.size}))
app.get('/status/:accountKey',async(req:any)=>{auth(req);const a=await accountRow(req.params.accountKey);const live=sockets.get(req.params.accountKey);return{accountKey:a.account_key,status:a.status,connectionState:live?.connection||a.connection_state,phoneE164:live?.phone||a.phone_e164,qrCode:live?.qr||a.qr_code,qrCreatedAt:a.qr_created_at,lastConnectedAt:a.last_connected_at,lastDisconnectCode:a.last_disconnect_code,lastDisconnectMessage:a.last_disconnect_message}})
app.get('/capabilities/:accountKey',async(req:any)=>{auth(req);await accountRow(req.params.accountKey);return {transport:'baileys',accountKey:req.params.accountKey,capabilities:{text:true,buttons:true,location_request:false,location_receive:true,media_send:true,media_receive:true,documents:true,voice_notes:true,delivery_status:true}}})
app.post('/start',async(req:any)=>{auth(req);const body=req.body as any;if(!body?.accountKey)throw new Error('accountKey required');await start(body.accountKey);return{ok:true,accountKey:body.accountKey}})
app.post('/reset',async(req:any)=>{auth(req);const body=req.body as any;const a=await accountRow(body.accountKey);const live=sockets.get(body.accountKey);try{live?.sock?.end?.(new Error('operator reset'))}catch{}sockets.delete(body.accountKey);await pool.query('delete from wa_auth_creds where account_id=$1',[a.id]);await pool.query('delete from wa_auth_keys where account_id=$1',[a.id]);await pool.query("update wa_accounts set status='stopped',connection_state='close',qr_code=null,updated_at=now() where id=$1",[a.id]);return{ok:true}})
app.post('/send',async(req:any)=>{auth(req);const body=req.body as any;if(!body?.accountKey)throw Object.assign(new Error('accountKey required'),{statusCode:400});const a=sockets.get(String(body.accountKey));if(!a?.sock)throw Object.assign(new Error('WhatsApp account not connected'),{statusCode:409});const to=jid(String(body.to));let result:any;if(body.type==='text')result=await a.sock.sendMessage(to,{text:String(body.text||'')});else if(body.type==='buttons')result=await a.sock.sendMessage(to,{text:String(body.body||''),buttons:(body.buttons||[]).slice(0,3).map((b:any)=>({buttonId:String(b.id),buttonText:{displayText:String(b.title)},type:1})),headerType:1});else if(body.type==='location_request')result=await a.sock.sendMessage(to,{text:String(body.body||'Please share your location.')});else throw Object.assign(new Error('unsupported message type'),{statusCode:400});return{ok:true,messageId:result?.key?.id||null,raw:result}})

app.addHook('onRequest',async(req,reply)=>{if(['/healthz'].includes(req.url.split('?')[0]))return;try{auth(req)}catch(e:any){return reply.code(e.statusCode||401).send({error:'unauthorized'})}})

const bootstrap=async()=>{if(!env.db||!env.apiKey||!env.webhookSecret||!env.webhookUrl||!env.mediaUrl)throw new Error('DATABASE_URL, OPERATOR_API_KEY, WEBHOOK_SECRET, MAIN_APP_WEBHOOK_URL and MAIN_APP_MEDIA_URL are required');if(env.appEnv==='production' && /localhost|127\.0\.0\.1/.test(env.webhookUrl))throw new Error('MAIN_APP_WEBHOOK_URL must not point to localhost in production');if(env.appEnv==='production' && /localhost|127\.0\.0\.1/.test(env.mediaUrl))throw new Error('MAIN_APP_MEDIA_URL must not point to localhost in production');await app.listen({port:env.port,host:'0.0.0.0'});const rows=await pool.query("select account_key from wa_accounts where status in ('connected','pairing','reconnecting')");for(const r of rows.rows)void start(r.account_key);}
bootstrap().catch(err=>{log.error(err,'operator failed to boot');process.exit(1)})
process.on('SIGTERM',async()=>{for(const a of sockets.values())try{a.sock?.end?.(new Error('shutdown'))}catch{}await pool.end();process.exit(0)})
