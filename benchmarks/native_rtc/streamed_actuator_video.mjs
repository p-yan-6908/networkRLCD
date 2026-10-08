// Namespace-only video adapter; no changed source/encoder or legacy role guards.
import {loadRecordedVideo as loadV5,VIDEO_QUALITY_PROTOCOL,pairRecordedQuality} from './streamed_video5.mjs';
export {VIDEO_QUALITY_PROTOCOL,pairRecordedQuality};
export function legacyVideoConfig(config){
 if(config.source_kind!=='recorded_video_actuator_identification_v1'||!['discovery','replication'].includes(config.collection_config?.role))throw Error('declared diagnostic role/source required');
 return {...config,source_kind:'recorded_video_repair_v5'};
}
export async function loadRecordedVideo(config){return loadV5(legacyVideoConfig(config));}
