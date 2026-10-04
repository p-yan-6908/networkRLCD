// Recorded content is labels-only. No movie pixels/time/segment enters policy observations.
import {QUALITY_PROTOCOL,computeRgbQuality} from './source_quality.mjs';
export const VIDEO_QUALITY_PROTOCOL=Object.freeze({...QUALITY_PROTOCOL,source:'recorded video; reference RGB sampled before the owned capture request'});
export function sampleSourceRgb(ctx){const p=QUALITY_PROTOCOL,data=ctx.getImageData(0,0,p.width,p.height).data,rgb=[];for(let y=p.grid_start;y<p.height;y+=p.grid_step){if(y>=p.exclude_marker_y_min&&y<=p.exclude_marker_y_max)continue;for(let x=p.grid_start;x<p.width;x+=p.grid_step){const o=(y*p.width+x)*4;rgb.push(data[o],data[o+1],data[o+2]);}}return rgb;}
export function pairRecordedQuality(ctx,reference){const observed=sampleSourceRgb(ctx);return {...computeRgbQuality(observed,reference),observed_rgb:observed,reference_rgb:reference};}
export async function loadRecordedVideo(config){
 if(config?.source_kind!=='recorded_video_v1')return null;
 const [start,end]=config.video_segment;if(!Number.isInteger(start)||!Number.isInteger(end)||end-start<20000)throw Error('recorded segment required');
 const response=await fetch('/recorded-video.mp4');if(!response.ok)throw Error('recorded video load failed');const bytes=await response.arrayBuffer();
 const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');if(sha!==config.video_sha256)throw Error('recorded source bytes changed');
 const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='auto';video.src=URL.createObjectURL(new Blob([bytes],{type:'video/mp4'}));
 const event=name=>Promise.race([new Promise((resolve,reject)=>{video.addEventListener(name,resolve,{once:true});video.addEventListener('error',()=>reject(Error('recorded source decode failed')),{once:true});}),new Promise((_,reject)=>setTimeout(()=>reject(Error('recorded source timeout')),10000))]);
 await event('loadedmetadata');video.currentTime=start/1000;await event('seeked');if(video.readyState<2)await event('loadeddata');
 return {video,segment:[start,end],sha256:sha,draw(ctx){if(video.currentTime*1000>=end)throw Error('recorded source reservation exhausted');const aspect=640/360,ratio=video.videoWidth/video.videoHeight;let sx=0,sy=0,sw=video.videoWidth,sh=video.videoHeight;if(ratio>aspect){sw=sh*aspect;sx=(video.videoWidth-sw)/2;}else{sh=sw/aspect;sy=(video.videoHeight-sh)/2;}ctx.drawImage(video,sx,sy,sw,sh,0,0,640,360);return {source_media_ms:video.currentTime*1000,reference_rgb:sampleSourceRgb(ctx)};},start:()=>video.play(),stop(){video.pause();URL.revokeObjectURL(video.src);}};
}
