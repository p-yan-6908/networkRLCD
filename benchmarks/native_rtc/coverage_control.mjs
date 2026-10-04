// Legal train/calibration coverage only; fixed exploration is not learned control.
import {RepairPolicy,CONFIG,SenderContentEncoder,warmRepair} from './dense_control.mjs';
export {RepairPolicy,CONFIG,SenderContentEncoder,warmRepair};
export const COVERAGE_CAPS=Object.freeze([400000,450000,500000]);
export const BEHAVIORS=Object.freeze(['fixed400','fixed450','fixed500']);
export function explorationCap(behavior,step,seed,observation){const f=observation.features;if(!BEHAVIORS.includes(behavior)||!Array.isArray(f)||f.length!==16||!f.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=0)||![0,1].includes(f[9]))throw Error('declared exact-cap exploration and causal sender features required');return COVERAGE_CAPS[BEHAVIORS.indexOf(behavior)];}
