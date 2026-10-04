// Paired sampled RGB error for owned synthetic content, NOT VMAF/human QoE.
export const QUALITY_PROTOCOL=Object.freeze({metric:'paired_sampled_rgb_psnr',width:640,height:360,grid_step:16,grid_start:8,exclude_marker_y_min:318,exclude_marker_y_max:347,max_pixel_value:255,channels_per_frame:2400,source:'deterministic generated canvas; source ID decoded from received pixels',labels_only:true});
export function drawSourceScene(ctx,n){ctx.fillStyle='hsl('+((n*7)%360)+',70%,45%)';ctx.fillRect(0,0,640,360);for(let i=0;i<30;i++){ctx.fillStyle='hsl('+((n*13+i*31)%360)+',80%,65%)';ctx.fillRect((n*7+i*23)%640,(i*17+n*3)%360,30,25);}ctx.fillStyle='white';ctx.font='24px monospace';ctx.fillText('RLCD local '+n,12,35);}
export function computeRgbQuality(observed,reference){
 if(!observed||!reference||observed.length!==reference.length||!observed.length||observed.length%3!==0)throw Error('aligned nonempty RGB samples required');
 let sum=0;for(let i=0;i<observed.length;i++){for(const value of [observed[i],reference[i]])if(!Number.isInteger(value)||value<0||value>255)throw Error('byte RGB sample required');const difference=observed[i]-reference[i];sum+=difference*difference;}
 const mse=sum/observed.length;return {rgb_mse:mse,psnr_db:mse===0?null:10*Math.log10(255*255/mse),exact_match:mse===0,channels:observed.length};
}
export function samplePairedQuality(observedCtx,referenceCtx){
 const p=QUALITY_PROTOCOL,a=observedCtx.getImageData(0,0,p.width,p.height).data,b=referenceCtx.getImageData(0,0,p.width,p.height).data,observed=[],reference=[];
 for(let y=p.grid_start;y<p.height;y+=p.grid_step){if(y>=p.exclude_marker_y_min&&y<=p.exclude_marker_y_max)continue;for(let x=p.grid_start;x<p.width;x+=p.grid_step){const offset=(y*p.width+x)*4;for(let c=0;c<3;c++){observed.push(a[offset+c]);reference.push(b[offset+c]);}}}
 if(observed.length!==p.channels_per_frame)throw Error('quality sampling geometry mismatch');
 return {...computeRgbQuality(observed,reference),observed_rgb:observed,reference_rgb:reference};
}
