// Namespace-only adapter; unchanged owned-inode V5 movie loader and encoder physics.
import {loadRecordedVideo as loadV5,VIDEO_QUALITY_PROTOCOL,pairRecordedQuality} from './streamed_video5.mjs';
export {VIDEO_QUALITY_PROTOCOL,pairRecordedQuality};
export function legacyVideoConfig(config){if(config.source_kind!=='recorded_video_action_outcome_live_v1')throw Error('declared action-outcome live source required');return {...config,source_kind:'recorded_video_repair_v5'};}
export async function loadRecordedVideo(config){return loadV5(legacyVideoConfig(config));}
