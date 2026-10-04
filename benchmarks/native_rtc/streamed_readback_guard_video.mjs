// Namespace only: source ownership, encoder, fixed geometry/FPS and labels unchanged.
import {loadRecordedVideo as loadV5,VIDEO_QUALITY_PROTOCOL,pairRecordedQuality} from './streamed_video5.mjs';
export {VIDEO_QUALITY_PROTOCOL,pairRecordedQuality};
export async function loadRecordedVideo(config){if(config.source_kind!=='recorded_video_readback_guard_v1')throw Error('declared readback guard source required');return loadV5({...config,source_kind:'recorded_video_repair_v5'});}
