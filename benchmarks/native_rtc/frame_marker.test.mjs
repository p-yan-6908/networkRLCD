import test from 'node:test';
import assert from 'node:assert/strict';
import {crc8,markerBits,decodeMarkerBits,writeFrameMarker,readFrameMarker,GEOMETRY,FRAME_PROTOCOL} from './frame_marker.mjs';
test('CRC-8/SMBUS independent standard check vector',()=>assert.equal(crc8(new TextEncoder().encode('123456789')),0xf4));
test('boundary frame IDs roundtrip without signed-bit confusion',()=>{for(const id of [0,1,255,256,32768,65535])assert.equal(decodeMarkerBits(markerBits(id)),id);});
test('every single-bit change is detected, never made a safe label',()=>{const bits=markerBits(2026);for(let i=0;i<24;i++){const bad=bits.slice();bad[i]^=1;assert.equal(decodeMarkerBits(bad),null);}});
test('invalid encoder IDs and bytes reject',()=>{for(const id of [-1,65536,1.5,NaN])assert.throws(()=>markerBits(id));assert.throws(()=>crc8([256]));});
test('malformed decoder shapes return no identity',()=>{assert.equal(decodeMarkerBits(null),null);assert.equal(decodeMarkerBits(new Array(23).fill(0)),null);assert.equal(decodeMarkerBits(new Array(24).fill(2)),null);});
test('draw uses black/white rectangles at the declared video geometry',()=>{const calls=[],ctx={fillStyle:null,fillRect(...args){calls.push({color:this.fillStyle,args});}};writeFrameMarker(ctx,1234);assert.equal(calls.length,25);for(let i=0;i<24;i++){assert.deepEqual(calls[i+1].args,[GEOMETRY.x+i*24,GEOMETRY.y,20,20]);assert.equal(calls[i+1].color,markerBits(1234)[i]?'white':'black');}});
function pixels(id,flip=-1){const bits=markerBits(id),w=GEOMETRY.cell*GEOMETRY.bits,p=new Uint8ClampedArray(w*GEOMETRY.square*4);for(let y=0;y<GEOMETRY.square;y++)for(let x=0;x<w;x++){const bit=bits[Math.floor(x/24)]^(Math.floor(x/24)===flip?1:0),i=(y*w+x)*4;p[i]=p[i+1]=p[i+2]=bit?245:10;p[i+3]=255;}return {getImageData(){return {data:p};}};}
test('readback uses real sampled luminance, tolerates YUV-like level changes',()=>{const r=readFrameMarker(pixels(4567));assert.equal(r.source_id,4567);assert.equal(r.luma.length,24);assert.ok(r.luma.every(x=>x===10||x===245));});
test('pixel corruption remains unknown instead of substituting a source ID',()=>assert.equal(readFrameMarker(pixels(4567,10)).source_id,null));
test('deadline/censor/coverage conventions are frozen before native data',()=>{assert.equal(FRAME_PROTOCOL.deadline_ms,150);assert.equal(FRAME_PROTOCOL.min_known_marker_coverage,0.95);assert.equal(FRAME_PROTOCOL.terminal_censoring,'exclude_all_requests_with_deadline_after_cutoff');assert.ok(Object.isFrozen(FRAME_PROTOCOL));});
