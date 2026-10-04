import {loadRecordedVideo as loadV2,VIDEO_QUALITY_PROTOCOL,pairRecordedQuality} from './streamed_video.mjs';
export {VIDEO_QUALITY_PROTOCOL,pairRecordedQuality};
export function legacyVideoConfig(config){if(config.source_kind!=='recorded_video_repair_v5')throw Error('versioned repair5 source required');return {...config,source_kind:'recorded_video_repair_v2'};}
export async function loadRecordedVideo(config){return loadV2(legacyVideoConfig(config));}
