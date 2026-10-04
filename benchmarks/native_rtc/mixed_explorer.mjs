import {explorationOrder} from './block_explorer.mjs';
export class NativeMixedExplorer{
 constructor(seed,start,blockMs){if(!Number.isFinite(start)||start<0||![250,1000,4000].includes(blockMs))throw Error('frozen mixed behavior clock/dwell required');this.order=explorationOrder(seed);this.protocol=Object.freeze({controller:'native_mixed_block_exploration_v3',seed,block_ms:blockMs,block_start_ms:start,cap_order:this.order,receiver_target_ms:0,behavior_is_not_the_learned_policy:true});}
 action(now){if(!Number.isFinite(now)||now<this.protocol.block_start_ms)throw Error('noncausal mixed behavior time');return {encoder_max_bitrate_bps:this.order[Math.floor((now-this.protocol.block_start_ms)/this.protocol.block_ms)%7],receiver_jitter_buffer_target_ms:0};}
}
