import test from 'node:test';
import assert from 'node:assert/strict';
import {sampleSourceRgb,pairRecordedQuality,VIDEO_QUALITY_PROTOCOL,loadRecordedVideo} from './recorded_video.mjs';
test('recorded reference samples exclude marker rows and retain RGB geometry',()=>{const data=new Uint8ClampedArray(640*360*4);for(let y=318;y<=347;y++)for(let x=0;x<640;x++)data[(y*640+x)*4]=255;const ctx={getImageData:()=>({data})};const rgb=sampleSourceRgb(ctx);assert.equal(rgb.length,2400);assert.ok(rgb.every(n=>n===0));const paired=pairRecordedQuality(ctx,rgb);assert.equal(paired.rgb_mse,0);assert.equal(paired.exact_match,true);assert.equal(paired.psnr_db,null);});
test('recorded quality protocol is distinct and labels-only',()=>{assert.equal(VIDEO_QUALITY_PROTOCOL.labels_only,true);assert.match(VIDEO_QUALITY_PROTOCOL.source,/before the owned capture/);});
test('legacy generation does not load, fetch or reinterpret video',async()=>{assert.equal(await loadRecordedVideo({source_kind:'generated_canvas'}),null);});
test('missing or short recorded segments reject before network access',async()=>{await assert.rejects(loadRecordedVideo({source_kind:'recorded_video_v1',video_segment:[0,1]}),/segment/);});
