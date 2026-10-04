import {loadRecordedVideo as loadV2,VIDEO_QUALITY_PROTOCOL,pairRecordedQuality} from './streamed_video.mjs';
export {VIDEO_QUALITY_PROTOCOL,pairRecordedQuality};
export async function loadRecordedVideo(config){if(config.source_kind!=='recorded_video_repair_v3')throw Error('versioned repair3 source required');return loadV2({...config,source_kind:'recorded_video_repair_v2'});}
